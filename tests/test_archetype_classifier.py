from utils.archetype_classifier import ArchetypeClassifier


def test_classifier_loads_modern_format():
    classifier = ArchetypeClassifier()
    bundle = classifier.loader.get("Modern")
    assert bundle is not None
    assert bundle.specifics  # ensure archetype definitions present
