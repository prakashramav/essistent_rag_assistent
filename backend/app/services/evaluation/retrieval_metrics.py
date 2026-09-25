from typing import Any, List, Set


class RetrievalMetricsCalculator:
    @staticmethod
    def calculate_precision_at_k(
        retrieved: List[Any],
        relevant: Set[Any],
        k: int,
    ) -> float:
        """
        Precision@K: What proportion of retrieved items in top-K are relevant?
        precision@k = |retrieved[:k] ∩ relevant| / min(k, len(retrieved))
        """
        if not retrieved or not relevant or k <= 0:
            return 0.0
        top_k = retrieved[:k]
        hits = sum(1 for item in top_k if item in relevant)
        denominator = min(k, len(top_k))
        return hits / denominator if denominator > 0 else 0.0

    @staticmethod
    def calculate_recall_at_k(
        retrieved: List[Any],
        relevant: Set[Any],
        k: int,
    ) -> float:
        """
        Recall@K: What proportion of all relevant items were found in top-K?
        recall@k = |retrieved[:k] ∩ relevant| / |relevant|
        """
        if not relevant:
            return 1.0  # If no ground truth specified, recall is trivially satisfied
        if not retrieved:
            return 0.0
        top_k = retrieved[:k]
        hits = sum(1 for item in top_k if item in relevant)
        return hits / len(relevant)

    @staticmethod
    def calculate_mrr(
        retrieved: List[Any],
        relevant: Set[Any],
    ) -> float:
        """
        Mean Reciprocal Rank (MRR): 1 / rank of the first relevant item.
        Returns 0.0 if no relevant items are found.
        """
        if not retrieved or not relevant:
            return 0.0
        for rank, item in enumerate(retrieved, start=1):
            if item in relevant:
                return 1.0 / rank
        return 0.0

    @staticmethod
    def calculate_hit_rate(
        retrieved: List[Any],
        relevant: Set[Any],
        k: int,
    ) -> float:
        """Hit Rate@K: 1.0 if at least one relevant item is in top-K, else 0.0."""
        if not retrieved or not relevant or k <= 0:
            return 0.0
        for item in retrieved[:k]:
            if item in relevant:
                return 1.0
        return 0.0
