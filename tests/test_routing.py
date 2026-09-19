from engine.router.capability_registry import CapabilityRegistry
from engine.router.classifier import classify_step
from engine.router.router import Router
from engine.schemas import Capability, StepType


def test_verify_routes_to_no_model():
    features = classify_step("run tests", step_type=StepType.VERIFY, has_tests=True, has_strong_validation=True)
    route = Router(CapabilityRegistry()).route(features, "t1")
    assert route.capability == Capability.NO_MODEL


def test_security_floor_is_deep():
    features = classify_step("fix OAuth permission validation", step_type=StepType.BUILD, predicted_write_files=["auth.py"], has_tests=True)
    route = Router(CapabilityRegistry()).route(features, "t2")
    assert CapabilityRegistry.order(route.capability) >= CapabilityRegistry.order(Capability.DEEP)


def test_large_untested_write_is_deep():
    features = classify_step("refactor these modules", step_type=StepType.BUILD, predicted_write_files=[f"f{i}.py" for i in range(6)], has_tests=False)
    route = Router(CapabilityRegistry()).route(features, "t3")
    assert CapabilityRegistry.order(route.capability) >= CapabilityRegistry.order(Capability.DEEP)


def test_explicit_model_override_resolves_without_changing_policy():
    reg = CapabilityRegistry({Capability.BUILD: "test-model"})
    assert reg.resolve(Capability.BUILD).model_id == "test-model"
