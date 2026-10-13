"""Source syntax, literal/contact offsets and secret-reference boundaries."""
import ast
import json
import re
from types import SimpleNamespace
import pytest
from usr.plugins.local_privacy_guard.helpers.code_regions import analysis_text, regions
from usr.plugins.local_privacy_guard.helpers.pii_detector import PIIFilter
from usr.plugins.local_privacy_guard.helpers.secrets import check, SecretError


@pytest.mark.parametrize('source', [
    'class CustomerService:\n    PORT = 59022\n    def Customer(self):\n        return self.PORT\n',
    'const CustomerService = 59022;\nfunction Customer(user_input) { return user_input; }',
    'interface CustomerService { Customer: number; }\nconst PORT: number = 59022;',
])
def test_source_syntax_and_numeric_constants_are_not_detection_input(source):
    scan = analysis_text(source)
    assert regions(source)
    assert len(scan) == len(source) and scan.count('\n') == source.count('\n')
    assert not scan.strip()
    assert PIIFilter({'use_ner':False}).filter(source).filtered_text == source


@pytest.mark.parametrize('source', [
    'class CustomerService:\n    email = "anna@example.invalid"\n    # Contact ben@example.invalid\n',
    'class CustomerService:\r\n    email = "anna@example.invalid"\r\n    # Contact ben@example.invalid\r\n',
    'const CustomerService = "anna@example.invalid"; // Contact ben@example.invalid',
    '/* Contact ben@example.invalid */\nconst CustomerService = `anna@example.invalid`;',
    'class CustomerService:\n    note = """Contact anna@example.invalid\nben@example.invalid"""\n',
])
def test_literal_and_comment_contacts_keep_exact_original_offsets(source):
    result = PIIFilter({'use_ner':False}).filter(source)
    assert {hit.original for hit in result.detections if hit.pii_type == 'EMAIL'} == {'anna@example.invalid','ben@example.invalid'}
    assert 'CustomerService' in result.filtered_text
    for hit in result.detections:
        assert source[hit.start:hit.end] == hit.original


def test_names_in_literals_and_comments_but_not_identifiers(monkeypatch):
    from usr.plugins.local_privacy_guard.helpers import pii_detector as pd
    def pipe(texts, batch_size):
        for text in texts:
            yield SimpleNamespace(ents=[SimpleNamespace(start_char=m.start(),end_char=m.end(),text=m[0],label_='PERSON') for m in re.finditer(r'CustomerService|Anna Muster',text)])
    monkeypatch.setattr(pd,'_get_nlp',lambda lang:SimpleNamespace(meta={},pipe=pipe))
    source = 'class CustomerService:\n    name = "Anna Muster"\n    # Anna Muster\n'
    result = pd.PIIFilter({'languages':['en']}).filter(source)
    assert [hit.original for hit in result.detections] == ['Anna Muster','Anna Muster']
    ast.parse(result.filtered_text)


def test_ner_cannot_bridge_two_literals_and_replace_syntax(monkeypatch):
    from usr.plugins.local_privacy_guard.helpers import pii_detector as pd
    scanner = pd.PIIFilter({'use_regex':False,'use_ner':True})
    def cross(text):
        start, end = text.index('Anna'), text.index('Muster') + len('Muster')
        return [pd.PIIDetection('PERSON',text[start:end],start,end,'<PERSON>','ner')]
    monkeypatch.setattr(scanner,'_detect_ner',cross)
    source = 'a = "Anna"; b = "Muster"'
    assert scanner.filter(source).filtered_text == source


@pytest.mark.parametrize('source', [
    '```python\nAnna Muster\n```', '```javascript\nconst Anna Muster\n```',
    '```javascript\nconst name = Μαρία Παπαδοπούλου\n```',
    '```python\nclass CustomerService:\n', '```unknown\nAnna Muster\n```',
    'const CustomerService = `Hello ${user.name}`;', 'const CustomerService = /Anna/;',
    'name = f"Hello {user.name}"', 'Contact Anna Muster at anna@example.invalid.',
])
def test_ambiguous_incomplete_or_unsupported_source_stays_ordinary_text(source):
    assert analysis_text(source) == source


def test_mixed_text_inline_and_file_label_preserve_only_source_syntax():
    source = 'Contact Anna Muster.\n```customer.py\nclass CustomerService:\n    email = "anna@example.invalid"\n```\nUse `CustomerService.create(user_input)`.'
    scan = analysis_text(source)
    assert 'Contact Anna Muster.' in scan and 'anna@example.invalid' in scan
    assert 'class CustomerService' not in scan and 'CustomerService.create' not in scan


def test_unquoted_email_and_explicit_custom_rules_cannot_hide_in_code():
    scanner = PIIFilter({'use_ner':False,'custom_patterns':[{'name':'CUSTOM','regex':'CustomerService'}]})
    result = scanner.filter('CustomerService = anna@example.invalid')
    assert {hit.pii_type for hit in result.detections} == {'CUSTOM','EMAIL'}


@pytest.mark.parametrize('source', [
    'note = "`CustomerService.create(user_input)`"',
    'note = """\n```python\nclass CustomerService: pass\n```\n"""',
    'const note = "`CustomerService.create(user_input)`";',
])
def test_markdown_inside_source_literals_is_still_data(source):
    assert 'CustomerService' in analysis_text(source)


@pytest.mark.parametrize('source', [
    'note = f"""Hello {user.name}\n```python\nclass CustomerService: pass\n```\n"""',
    'const note = `Hello ${user.name}\n\u0060\u0060\u0060python\nclass CustomerService: pass\n\u0060\u0060\u0060`;',
    'note = f"Hello {user.name} `CustomerService.create(user_input)`"',
])
def test_unsupported_outer_source_cannot_exempt_markdown_inside_literal_data(source):
    assert analysis_text(source) == source


@pytest.mark.parametrize('source', [
    'api_key = os.getenv("API_KEY")', 'password = user_input',
    'label = "Änderung"; api_key = os.getenv("API_KEY")',
    'password = settings["password"]', 'api_key = os.environ["API_KEY"]',
    'def login(value):\n    password = value\n    return password',
    'from configuration import cfg\npassword = cfg.password',
    '```python\napi_key = os.getenv("API_KEY")\n```',
    'const api_key = process.env.API_KEY;', 'const password = process.env["PASSWORD"];',
    json.dumps({'code':'api_key = os.getenv("API_KEY")'}),
    '```json\n' + json.dumps({'code':'api_key = os.getenv("API_KEY")'}) + '\n```',
])
def test_recognized_references_are_not_literal_secrets(source):
    check(source)


@pytest.mark.parametrize('source', [
    'password="hunter2"', 'password=hunter2',
    'api_key = os.getenv("API_KEY", "hunter2")',
    'api_key = os.getenv("API_KEY") + "hunter2"',
    'user_input = "hunter2"\npassword = user_input',
    'const password = "hunter2";', 'const password = process.env.PASSWORD || "hunter2";',
    '```python\n# password="hunter2"\nclass CustomerService: pass\n```',
    json.dumps({'api_key':'os.getenv("API_KEY")'}),
    json.dumps({'code':'password="hunter2"'}),
    'const password = process.env.PASSWORD;\n// -----BEGIN PRIVATE KEY-----',
])
def test_literal_fallback_comment_and_serialized_secrets_remain_blocked(source):
    with pytest.raises(SecretError) as error:
        check(source)
    assert 'hunter2' not in str(error.value)


def test_known_credentials_are_never_exempted_by_code():
    with pytest.raises(SecretError):
        check('api_key = os.getenv("SYNTHETIC_MANAGED_SECRET")', ['SYNTHETIC_MANAGED_SECRET'])


def test_large_source_uses_normal_checks_without_parser_work():
    source = 'class CustomerService:\n' + '    # anna@example.invalid\n' * 10_000
    assert analysis_text(source) == source


def test_deep_structured_content_stops_with_a_safe_error():
    payload = 'ordinary text'
    for _ in range(40):
        payload = [payload]
    with pytest.raises(SecretError,match='depth limit'):
        check(json.dumps(payload))
