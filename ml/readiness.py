def compute_readiness(skill_score, resume_score):
    overall = round(
        0.6 * skill_score +
        0.4 * resume_score
    )
    return overall
