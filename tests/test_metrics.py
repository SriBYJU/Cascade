from engine.metrics.usage import UsageTotals
from engine.metrics.savings import verified_work_per_expensive_token


def test_head_and_total_tokens_are_both_reported():
    u = UsageTotals(head_input_tokens=10, head_output_tokens=5, worker_input_tokens=30, worker_output_tokens=10)
    assert u.head_tokens == 15
    assert u.total_tokens == 55
    assert u.to_dict()["head_tokens"] != u.to_dict()["total_tokens"]


def test_vwet():
    assert verified_work_per_expensive_token(10, 2) == 5
