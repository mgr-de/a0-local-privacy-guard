"""Recognize source syntax locally; comments/literals remain detection input.

No execution, imports from user code, external parsers or model calls. Unsupported
or incomplete source is ordinary text. Offsets and newlines are preserved.
"""
import ast
from dataclasses import dataclass
import io
import re
import tokenize

POLICY_VERSION = 'code-regions-v2'
LIMIT = 200_000
PYTHON = {'py', 'python'}
JAVASCRIPT = {'js', 'javascript', 'ts', 'typescript'}
SUFFIXES = {'.py': 'python', '.js': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript', '.ts': 'typescript'}
FENCE = re.compile(r'(?m)^ {0,3}(`{3,}|~{3,})([^\n]*)\n')
JS_START = re.compile(r'(?m)^\s*(?:(?:export\s+)?(?:const|let|var|function|class|interface|type)\b|(?:async\s+)?function\b)')
CREDENTIAL = re.compile(r'(?i)^(?:password|passwd|passwort|api_?key|access_?token|client_?secret|authorization)$')


@dataclass
class Region:
    start: int
    end: int
    data: list
    references: list


def _offsets(text):
    starts = [0]
    for match in re.finditer('\n', text):
        starts.append(match.end())
    return starts


def _ast_offset(text, starts, node, end=False):
    row = node.end_lineno if end else node.lineno
    column = node.end_col_offset if end else node.col_offset
    base = starts[row - 1]
    # AST columns count UTF-8 bytes; tokenize columns count characters.
    return base + len(text[base:].encode('utf-8')[:column].decode('utf-8'))


def _reference(node, declared=(), assigned=None, seen=()):
    assigned = assigned or {}
    if isinstance(node, ast.Name):
        if node.id in assigned:
            return node.id not in seen and _reference(assigned[node.id], declared, assigned, (*seen, node.id))
        return node.id in declared or node.id in {'os', 'config', 'settings', 'credentials', 'user_input', 'userInput', 'process'}
    if isinstance(node, ast.Attribute):
        return _reference(node.value, declared, assigned, seen)
    if isinstance(node, ast.Subscript):
        return _reference(node.value, declared, assigned, seen) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str) and bool(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', node.slice.value))
    if isinstance(node, ast.Call):
        name = ast.unparse(node.func)
        return name in {'os.getenv', 'os.environ.get'} and len(node.args) == 1 and not node.keywords and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str) and bool(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', node.args[0].value))
    return False


def _python(source):
    try:
        tree = ast.parse(source)
        if any(isinstance(node, ast.JoinedStr) for node in ast.walk(tree)):
            return None
        if not tree.body or all(isinstance(n, ast.Expr) and not isinstance(n.value, ast.Call) for n in tree.body):
            return None  # Bare names, JSON/data and natural-language fragments.
        starts = _offsets(source)
        data = []
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type not in {tokenize.STRING, tokenize.COMMENT}:
                continue
            start = starts[tok.start[0] - 1] + tok.start[1]
            end = starts[tok.end[0] - 1] + tok.end[1]
            # Scan the literal, including escape spellings, without its prefix.
            if tok.type == tokenize.STRING:
                prefix = re.match(r'(?i)[rubf]*(?:\"\"\"|\'\'\'|\"|\')', tok.string)
                if not prefix:
                    return None
                if 'f' in tok.string[:prefix.end()].lower():
                    return None  # Do not guess at interpolated-expression bounds.
                quote = 3 if tok.string[prefix.end()-3:prefix.end()] in {'\"\"\"', "'''"} else 1
                start += prefix.end()
                end -= quote
            data.append((start, end))
        references = []
        declared = {n.arg for n in ast.walk(tree) if isinstance(n, ast.arg)}
        declared.update(alias.asname or alias.name.split('.')[0] for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names)
        assigned = {target.id: node.value for node in ast.walk(tree) if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name)}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, (ast.Name, ast.Attribute)) and CREDENTIAL.fullmatch(t.id if isinstance(t, ast.Name) else t.attr) for t in targets) and _reference(node.value, declared, assigned):
                    references.append((_ast_offset(source, starts, node.value), _ast_offset(source, starts, node.value, True)))
        return data, references
    except (SyntaxError, tokenize.TokenError, IndentationError, ValueError, RecursionError):
        return None


def _javascript(source):
    # Conservative lexer, not a JS compiler. JSX/templates/regex literals and
    # unbalanced/incomplete snippets stay ordinary text rather than guessed code.
    if not JS_START.search(source) or re.search(r'<[A-Za-z][^>]*>', source):
        return None
    data, references, stack = [], [], []
    i = 0
    while i < len(source):
        ch = source[i]
        if source.startswith('//', i):
            end = source.find('\n', i)
            end = len(source) if end < 0 else end
            data.append((i, end)); i = end
        elif source.startswith('/*', i):
            end = source.find('*/', i + 2)
            if end < 0:
                return None
            data.append((i, end + 2)); i = end + 2
        elif ch in {'\"', "'", '`'}:
            start, quote = i + 1, ch
            i += 1
            while i < len(source) and source[i] != quote:
                if source[i] == '\\':
                    i += 2
                elif source.startswith('${', i) and quote == '`':
                    return None
                elif source[i] == '\n' and quote != '`':
                    return None
                else:
                    i += 1
            if i >= len(source):
                return None
            data.append((start, i)); i += 1
        elif ch in '([{':
            stack.append(ch); i += 1
        elif ch in ')]}':
            if not stack or stack.pop() != {')':'(', ']':'[', '}':'{'}[ch]:
                return None
            i += 1
        elif ch == '/':
            return None  # Division/regex ambiguity: preserve normal checks.
        else:
            i += 1
    if stack:
        return None
    syntax = list(source)
    for start, end in data:
        # Include surrounding quotes when validating lexical adjacency.
        left = start - 1 if start and source[start-1] in '\"\'`' else start
        right = end + 1 if end < len(source) and source[end] in '\"\'`' else end
        syntax[left:right] = ' ' * (right - left)
    identifier = r'(?:[^\W\d]|[$])[\w$]*'
    words = re.findall(identifier + r'|[^\s]', ''.join(syntax))
    keywords = set('const let var function class interface type export default async await return throw new extends implements public private protected static readonly import from as if else for of in while typeof instanceof void delete yield'.split())
    for previous, current in zip(words, words[1:]):
        if re.fullmatch(identifier, previous) and re.fullmatch(identifier, current) and previous not in keywords and current not in keywords:
            return None
    # Only complete environment/variable expressions, never fallback literals.
    expr = r'(?:process\.env\.[A-Za-z_][A-Za-z0-9_]*|process\.env\[[\"\'][A-Za-z_][A-Za-z0-9_]*[\"\']\])'
    assignment = re.compile(r'(?im)\b(?:password|passwd|passwort|api_?key|access_?token|client_?secret|authorization)\s*=\s*(' + expr + r')\s*(?=;|$)')
    for match in assignment.finditer(source):
        if not any(a <= match.start() < b for a, b in data):
            references.append(match.span(1))
    return data, references


def _parse(source, language=''):
    if len(source) > LIMIT:
        return None
    if language in PYTHON:
        return _python(source)
    if language in JAVASCRIPT:
        return _javascript(source)
    if language:
        return None
    if not re.search(r'(?m)^\s*(?:[\w.]+\s*(?::[^=\n]+)?=|(?:def|class|import|from|async|if|for|with|try)\b|[\w.]+\s*\()', source):
        return _javascript(source)
    return _python(source) or _javascript(source)


def regions(text, hint=''):
    if len(text) > LIMIT:
        return []
    language = SUFFIXES.get(next((s for s in SUFFIXES if hint.lower().endswith(s)), ''), hint.lower())
    # Parse an outer source file before Markdown inside its strings/docstrings.
    whole = _python(text) if FENCE.search(text) and language in PYTHON | {''} else (_parse(text, language) if not FENCE.search(text) else None)
    if whole is not None:
        return [Region(0, len(text), whole[0], whole[1])]
    # Once a payload begins as source/literal data, unsupported outer syntax
    # must not gain exemptions through Markdown embedded in its strings.
    if re.match(r'\s*(?:[\w.]+\s*(?::[^=\n]+)?=|(?:def|class|import|from|async|if|for|with|try|const|let|var|function|export|interface|type)\b|[rubfRUBF]*[\"\'])', text):
        return []
    found = []
    cursor = 0
    for opening in FENCE.finditer(text):
        if opening.start() < cursor:
            continue
        marker, label = opening.groups()
        closing = re.search(r'(?m)^ {0,3}' + re.escape(marker[0]) + '{' + str(len(marker)) + r',}[ \t]*$', text[opening.end():])
        if closing is None:
            continue
        end = opening.end() + closing.start()
        cursor = opening.end() + closing.end()
        label = label.strip().lower()
        language = SUFFIXES.get(next((suffix for suffix in SUFFIXES if label.endswith(suffix)), ''), label)
        parsed = _parse(text[opening.end():end], language)
        if parsed is not None:
            data, references = parsed
            found.append(Region(opening.end(), end, [(a+opening.end(),b+opening.end()) for a,b in data], [(a+opening.end(),b+opening.end()) for a,b in references]))
    for inline in re.finditer(r'(?<!`)`([^`\n]+)`(?!`)', text):
        if any(region.start <= inline.start() < region.end for region in found):
            continue
        parsed = _parse(inline[1])
        if parsed is not None:
            start, end = inline.span(1)
            found.append(Region(start, end, [(a+start,b+start) for a,b in parsed[0]], [(a+start,b+start) for a,b in parsed[1]]))
    if found:
        return found
    # A fence label alone never grants an exemption to invalid/unclosed code.
    if FENCE.search(text):
        return []
    return []


def analysis_text(text, hint=''):
    result = list(text)
    for region in regions(text, hint):
        for i in range(region.start, region.end):
            if text[i] not in '\r\n':
                result[i] = ' '
        for start, end in region.data:
            result[start:end] = text[start:end]
    return ''.join(result)


def assignment_references(text):
    return [span for region in regions(text) for span in region.references]
