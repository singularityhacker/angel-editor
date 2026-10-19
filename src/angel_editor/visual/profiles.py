import math


def resolve(strictness="moderate", profile=None, settings=None):
    settings, profile = settings or {}, profile or {}
    threshold = {"mild": 0.85, "lenient": 0.85, "moderate": 0.65, "strict": 0.45}[strictness]
    result = {}
    for category in ("nudity", "violence"):
        rule = {
            "enabled": True,
            "threshold": threshold,
            "review_threshold": threshold / 2,
            "min_duration": 0.25,
            "pad_before": 0.25,
            "pad_after": 0.25,
            "action": "skip",
        }
        rule.update(profile.get(category, {}))
        override = settings.get(f"{category}_threshold")
        if override is not None:
            rule["threshold"] = override
        for key in ("threshold", "review_threshold", "min_duration", "pad_before", "pad_after"):
            value = rule[key]
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid {category}.{key}")
        if rule["threshold"] > 1 or rule["review_threshold"] > 1:
            raise ValueError("Visual thresholds must be between 0 and 1")
        if rule["action"] not in {"skip", "flag"} or not isinstance(rule["enabled"], bool):
            raise ValueError("Visual rules require enabled boolean and action skip|flag")
        rule["review_threshold"] = min(rule["review_threshold"], rule["threshold"])
        result[category] = rule
    return result
