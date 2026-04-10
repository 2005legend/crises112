def compute_severity(incident, ai_data):
    score = 0

    if ai_data["incident_type"] == "fire":
        score += 5

    score += ai_data.get("affected", 0)

    if incident.get("reports", 1) > 3:
        score += 2

    if score >= 7:
        return "HIGH", score
    elif score >= 4:
        return "MEDIUM", score
    return "LOW", score