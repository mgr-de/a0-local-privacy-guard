"""Optional offline CPU ONNX inference. No Hub access or fallback at runtime."""
import hashlib
import json
import threading
from pathlib import Path

LABELS = {
    'GIVEN_NAME': 'PERSON', 'SURNAME': 'PERSON', 'COMPANY_NAME': 'ORGANISATION',
    'CITY': 'ORT', 'COUNTRY': 'ORT', 'STATE': 'ORT', 'EMAIL': 'EMAIL',
    'PHONE': 'TELEFON', 'FAX_NUMBER': 'TELEFON', 'IBAN': 'IBAN',
    'DATE': 'DATUM', 'DATE_OF_BIRTH': 'DATUM', 'TIME': 'DATUM',
    'CREDIT_DEBIT_CARD': 'KREDITKARTE', 'PASSPORT': 'REISEPASS',
    'SSN': 'SSN', 'TAX_ID': 'STEUER_ID', 'ZIP_CODE': 'PLZ',
    'STREET_ADDRESS': 'ADRESSE', 'STREET_NAME': 'ADRESSE',
    'SECONDARY_ADDRESS': 'ADRESSE', 'BUILDING_NUMBER': 'ADRESSE',
    'API_KEY': 'API_KEY', 'PASSWORD': 'CUSTOM', 'URL': 'URL',
    'ACCOUNT_NUMBER': 'CUSTOM', 'AGE': 'CUSTOM', 'CUSTOMER_ID': 'CUSTOM',
    'CVV': 'CUSTOM', 'DRIVERS_LICENSE': 'CUSTOM', 'EMPLOYEE_ID': 'CUSTOM',
    'GENDER': 'CUSTOM', 'GOVERNMENT_ID': 'CUSTOM', 'LICENSE_PLATE': 'CUSTOM',
    'MAC_ADDRESS': 'CUSTOM', 'MEDICAL_RECORD_NUMBER': 'CUSTOM', 'PIN': 'CUSTOM',
    'ROUTING_NUMBER': 'CUSTOM', 'SWIFT_BIC': 'CUSTOM', 'USERNAME': 'CUSTOM',
}
_models = {}
_lock = threading.RLock()


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def decode(text, predictions, labels, threshold):
    """Decode absolute character offsets; repair orphan I tags, merge name parts."""
    hits = []
    active = None
    for (start, end), index, score in predictions:
        label = labels[index]
        prefix, _, raw = label.partition('-')
        kind = LABELS.get(raw)
        if label == 'O' or score < threshold or not kind:
            if active:
                hits.append(tuple(active)); active = None
            continue
        if not 0 <= start < end <= len(text):
            raise ValueError('Invalid Nym token offsets.')
        continuation = active and kind == active[2] and (
            prefix == 'I' or (kind == 'PERSON' and text[active[1]:start].isspace()))
        if continuation:
            active[1] = end
            active[3] = min(active[3], score)
        else:
            if active:
                hits.append(tuple(active))
            active = [start, end, kind, score]
    if active:
        hits.append(tuple(active))
    return hits


class NymModel:
    def __init__(self, directory, threads, max_tokens, stride):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.np = np
        root = Path(directory).resolve()
        manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
        # Exact local artifact bundle, including tokenizer/model pairing.
        if set(manifest['files']) != {'model.onnx', 'tokenizer.json', 'config.json'}:
            raise ValueError('Incomplete Nym artifact manifest.')
        for filename, digest in manifest['files'].items():
            if sha256(root / filename) != digest:
                raise ValueError('Nym artifact checksum mismatch.')
        config = json.loads((root / 'config.json').read_text(encoding='utf-8'))
        self.labels = {int(k): v for k, v in config['id2label'].items()}
        if set(self.labels) != set(range(len(self.labels))) or 'O' not in self.labels.values():
            raise ValueError('Invalid Nym label configuration.')
        if any(v != 'O' and (v[:2] not in {'B-', 'I-'} or v[2:] not in LABELS) for v in self.labels.values()):
            raise ValueError('Unsupported Nym entity label.')
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(str(root / 'model.onnx'), options, providers=['CPUExecutionProvider'])
        inputs = {item.name: item.type for item in self.session.get_inputs()}
        if not {'input_ids', 'attention_mask'} <= set(inputs) or set(inputs) - {'input_ids', 'attention_mask', 'token_type_ids'}:
            raise ValueError('Unsupported Nym ONNX inputs.')
        if any(t != 'tensor(int64)' for t in inputs.values()):
            raise ValueError('Unsupported Nym ONNX input dtype.')
        self.inputs = inputs
        self.tokenizer = Tokenizer.from_file(str(root / 'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=max_tokens, stride=stride)
        self.identity = manifest
        self.lock = threading.RLock()

    def detect(self, text, threshold):
        # Tokenizer mutable internals and session concurrency are bounded here.
        with self.lock:
            encoding = self.tokenizer.encode(text)
            predictions = {}
            for chunk in [encoding, *encoding.overflowing]:
                arrays = {'input_ids': chunk.ids, 'attention_mask': chunk.attention_mask,
                          'token_type_ids': chunk.type_ids}
                feeds = {name: self.np.array([arrays[name]], dtype=self.np.int64) for name in self.inputs}
                logits = self.session.run(None, feeds)[0]
                if logits.shape != (1, len(chunk.ids), len(self.labels)) or not self.np.isfinite(logits).all():
                    raise ValueError('Invalid Nym ONNX output.')
                logits = logits[0] - logits[0].max(axis=-1, keepdims=True)
                probabilities = self.np.exp(logits)
                probabilities /= probabilities.sum(axis=-1, keepdims=True)
                for i, offsets in enumerate(chunk.offsets):
                    if chunk.special_tokens_mask[i] or offsets[0] == offsets[1]:
                        continue
                    margin = min(i, len(chunk.ids) - 1 - i)
                    label = int(probabilities[i].argmax())
                    candidate = (margin, label, float(probabilities[i, label]))
                    if offsets not in predictions or margin > predictions[offsets][0]:
                        predictions[offsets] = candidate
            ordered = [(offsets, item[1], item[2]) for offsets, item in sorted(predictions.items())]
            return decode(text, ordered, self.labels, threshold)


def get_model(config):
    """Load once per artifact stat identity; exceptions contain no paths or text."""
    try:
        directory = config.get('nym_model_dir')
        if not directory:
            raise ValueError('Missing model directory.')
        threads = int(config.get('nym_threads', 1))
        length = int(config.get('nym_max_tokens', 512))
        stride = int(config.get('nym_stride', 64))
        threshold = float(config.get('nym_threshold', .5))
        if not 1 <= threads <= 32 or not 32 <= length <= 8192 or not 0 < stride < length - 2 or not 0 <= threshold <= 1:
            raise ValueError('Invalid Nym inference settings.')
        root = Path(directory).resolve()
        stats = tuple((root / name).stat() for name in ('manifest.json', 'model.onnx', 'tokenizer.json', 'config.json'))
        key = (str(root), threads, length, stride, tuple((s.st_size, s.st_mtime_ns) for s in stats))
        with _lock:
            if key not in _models:
                model = NymModel(root, threads, length, stride)
                _models.clear()  # Bound retained model memory to one active bundle.
                _models[key] = model
            return _models[key]
    except Exception:
        raise ValueError('Optional Nym CPU detection unavailable. Install requirements-nym.txt and prepare a verified local model bundle; no fallback was used.') from None
