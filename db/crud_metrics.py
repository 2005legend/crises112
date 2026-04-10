from db.database import reports_col, incidents_col

def get_metrics():
    return {
        "total_reports": reports_col.count_documents({}),
        "total_incidents": incidents_col.count_documents({})
    }