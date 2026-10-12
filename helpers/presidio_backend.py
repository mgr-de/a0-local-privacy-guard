"""Optional local analyzer; shared spaCy instances, no downloads or second vault."""
from importlib.metadata import version, PackageNotFoundError
PIN='2.2.358'
restart_requested=False

def validate(languages):
    if restart_requested:raise ValueError('Optional packages were changed. Restart Agent Zero before using Presidio.')
    if not set(languages)<= {'de','en'}:
        raise ValueError('Presidio is currently tested only for German and English. Select the local backend for other languages.')
    try:
        if version('presidio-analyzer')!=PIN:raise ValueError('Install the tested Presidio version '+PIN+' and restart Agent Zero.')
        import presidio_analyzer
    except (ImportError,PackageNotFoundError):
        raise ValueError('Optional Presidio detection is unavailable. Install the optional dependencies, restart Agent Zero and run the local filter check.') from None

def detect_batch(texts,language,nlp,detector):
    validate(detector.ner_languages)
    from presidio_analyzer import AnalyzerEngine,RecognizerRegistry
    from presidio_analyzer.predefined_recognizers import SpacyRecognizer
    from presidio_analyzer.nlp_engine import SpacyNlpEngine,NerModelConfiguration
    from .pii_detector import LABEL_MAPS
    labels=dict(LABEL_MAPS.get(language,LABEL_MAPS['en']))
    if detector.ner_entity_types:
        labels={label:labels.get(label,label) for label in detector.ner_entity_types}
    engine=SpacyNlpEngine(models=[{'lang_code':language,'model_name':nlp.meta.get('name','installed')}],
        ner_model_configuration=NerModelConfiguration(model_to_presidio_entity_mapping=labels,
            labels_to_ignore=[],low_score_entity_names=[],default_score=.85))
    # Explicitly inject the already checked instance. Calling load() would allow
    # automatic model downloads; it must never run in model request processing.
    engine.nlp={language:nlp}
    registry=RecognizerRegistry(supported_languages=[language])
    registry.add_recognizer(SpacyRecognizer(supported_language=language,supported_entities=list(set(labels.values()))))
    variant=detector.config.get('presidio_variant','B')
    if variant not in {'A','B'}:raise ValueError('Unknown Presidio comparison configuration.')
    if variant=='B' and detector.use_regex:
        # Supplement the shared native regexes with contextual structured recognizers.
        from presidio_analyzer.predefined_recognizers import EmailRecognizer,PhoneRecognizer,IbanRecognizer
        for recognizer in (EmailRecognizer(supported_language=language),PhoneRecognizer(supported_language=language),IbanRecognizer(supported_language=language)):
            registry.add_recognizer(recognizer)
    analyzer=AnalyzerEngine(registry=registry,nlp_engine=engine,supported_languages=[language],log_decision_process=False)
    threshold=0.0 if variant=='A' else .35
    entities=list(set(labels.values()))+(['EMAIL_ADDRESS','PHONE_NUMBER','IBAN_CODE'] if variant=='B' and detector.use_regex else [])
    kinds={'EMAIL_ADDRESS':'EMAIL','PHONE_NUMBER':'TELEFON','IBAN_CODE':'IBAN'}
    for text,artifacts in engine.process_batch(texts,language,batch_size=32):
        hits=analyzer.analyze(text=text,language=language,entities=entities,nlp_artifacts=artifacts,
            score_threshold=threshold,return_decision_process=False)
        yield [(h.start,h.end,kinds.get(h.entity_type,h.entity_type),'ner',h.score,language) for h in hits
            if not (len(text[h.start:h.end].strip())==1 and text[h.start:h.end].strip().isalpha())]
