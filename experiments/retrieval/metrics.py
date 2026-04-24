from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean


def cosine_similarity(query: list[float], candidate: list[float]) -> float:
    return sum(left * right for left, right in zip(query, candidate))


@dataclass(frozen=True)
class RankedResult:
    item_id: str
    score: float
    is_relevant: bool


def recall_at_k(results: list[RankedResult], k: int) -> float:
    return 1.0 if any(result.is_relevant for result in results[:k]) else 0.0


def average_precision_at_k(results: list[RankedResult], k: int) -> float:
    relevant_seen = 0
    precision_sum = 0.0
    for index, result in enumerate(results[:k], start=1):
        if not result.is_relevant:
            continue
        relevant_seen += 1
        precision_sum += relevant_seen / index
    return precision_sum / relevant_seen if relevant_seen else 0.0


def ndcg_at_k(results: list[RankedResult], k: int) -> float:
    dcg = 0.0
    for index, result in enumerate(results[:k], start=1):
        if result.is_relevant:
            dcg += 1.0 / math.log2(index + 1)

    relevant_count = sum(1 for result in results if result.is_relevant)
    ideal = sum(1.0 / math.log2(index + 1) for index in range(1, min(k, relevant_count) + 1))
    if ideal == 0.0:
        return 0.0
    return dcg / ideal


def summarize_metric(values: list[float]) -> float:
    return mean(values) if values else 0.0
