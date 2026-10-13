# Code-aware text filtering (Local Privacy Guard 1.8.0)

Source code still passes through the normal guarded model boundary. Code recognition is local and does not run the supplied code, execute imports, call a model or install another detector. spaCy plus Regex remains the sole detector.

## Recognized source

Complete Python snippets are recognized with Python's AST and tokenizer. A conservative local lexer recognizes balanced JavaScript/TypeScript declarations. Supported Markdown labels include python/py, javascript/js and typescript/ts, plus .py/.js/.mjs/.cjs/.ts filename labels. Complete unlabelled snippets and parseable inline code expressions are also recognized. Structured source payloads can supply a language or filename/file_path/path hint for their code/source/content/text fields; hints never grant native protocol privileges.

Recognized syntax, identifiers and unquoted numeric constants do not enter name detection or broad format detection. Comments and written string-literal content still enter spaCy/Regex, with original character offsets and line breaks. A detected span cannot bridge the syntax between two literals. Recognizable raw emails, IBANs and key-like values are still checked outside literals, and explicit custom Regex rules take priority over syntax preservation.

Example: class CustomerService and PORT = 59022 remain unchanged. A contact email in a quoted default or a comment is replaced with a stable chat-owned token. Masked Python remains parseable for the tested literal/comment cases. Exact original code is restored locally when the model preserves those tokens; a model can still damage tokens or alter code.

Existing personal-name mappings do not rename a code identifier with the same spelling. Those known values remain checked in literals, comments and ordinary prose. Recognition results remain in the existing process-local span cache; no new source-text cache or persistence is introduced.

## Secrets and references

Managed credentials and recognizable private keys/API tokens are checked throughout the original content, including code and comments. Literal password/API-key assignments and literal fallback values continue to block the request.

Recognized Python references such as os.getenv("API_KEY"), os.environ["API_KEY"], settings["password"], selected conventional references and declared function parameters are allowed instead of being mistaken for literal credentials. A locally assigned literal cannot become an exempt reference merely by assigning it to another variable. JavaScript environment references such as process.env.API_KEY are supported. Unknown expressions remain conservative. This is limited syntax/reference recognition, not whole-program dataflow analysis.

JSON payloads are inspected recursively after decoding, so serializing code does not cause safe references to be mistaken for literals, and actual credential fields still block. JSON tags or arbitrary user-entered role/id/function fields do not gain protocol privileges.

## Conservative fallback

Incomplete/invalid source, unknown languages, JSX, Python f-strings, interpolated JS templates, JS regex/division ambiguity and source texts above 200,000 characters use ordinary text checks. Shell, SQL and YAML have no new syntax exemption. Unsupported code may therefore still receive false-positive replacements. Escaped strings are checked in their written representation by the PII detector; this is not general deobfuscation or a complete code privacy guarantee.

No profile settings, mappings, model routes, browser/image boundaries or provider presets are rewritten. Recognized code is not fully exempt from privacy checks. Source files on disk are unaffected by the model-payload filter.

## Verification

Regression cases cover Python/JS/TS syntax, numeric constants, mixed Markdown, literals/comments, offsets, cross-literal spans, invalid and unsupported code, serialized code, credential/reference handling, prior mappings, native dispatch and simulated actual wrapper transport with exact roundtrip. The suite makes no paid model call. Release-specific totals are recorded in the PR and release notes; historical reports describe their own earlier runs.
