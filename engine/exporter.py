"""
Módulo de Exportação e Persistência de Relatórios (JSON, CSV e Firebase Firestore).
"""

import json
import os
import csv
from typing import Optional
from engine.config import GlobalReconciliationReport


class ReportExporter:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def export_json(self, report: GlobalReconciliationReport) -> str:
        filepath = os.path.join(self.output_dir, f"report_{report.execution_id}.json")
        latest_path = os.path.join(self.output_dir, "latest_report.json")
        
        data = report.model_dump()
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return filepath

    def export_divergences_csv(self, report: GlobalReconciliationReport) -> str:
        filepath = os.path.join(self.output_dir, f"divergences_{report.execution_id}.csv")
        latest_path = os.path.join(self.output_dir, "latest_divergences.csv")

        fields = [
            "id",
            "source_lead_id",
            "email",
            "phone",
            "origin_channel",
            "divergence_type",
            "severity",
            "details",
            "source_created_at",
            "cv_created_at",
            "origem_no_cv",
            "integration_id",
        ]

        def write_rows(file_path):
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                for div in report.divergences:
                    writer.writerow(div.model_dump())

        write_rows(filepath)
        write_rows(latest_path)

        return filepath

    def save_to_firebase(self, report: GlobalReconciliationReport) -> bool:
        """Salva os relatórios no Firebase Firestore se o SDK / credenciais estiverem disponíveis."""
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            if not firebase_admin._apps:
                cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
                if cred_path and os.path.exists(cred_path):
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                else:
                    return False

            db = firestore.client()
            db.collection("reconciliations").document(report.execution_id).set(report.model_dump())
            return True
        except Exception:
            return False
