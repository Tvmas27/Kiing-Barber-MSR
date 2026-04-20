"""Firebase Admin bootstrap utilities."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import credentials


def initialize_firebase(base_dir: Path) -> None:
    """Initialize Firebase Admin once, if credentials are available."""
    if firebase_admin._apps:
        return

    firebase_creds = os.getenv('FIREBASE_CREDENTIALS')
    if not firebase_creds:
        print('Firebase no inicializado: falta FIREBASE_CREDENTIALS')
        return

    try:
        if firebase_creds.startswith('{'):
            cred_dict: dict[str, Any] = json.loads(firebase_creds)
            private_key = cred_dict.get('private_key')
            if isinstance(private_key, str):
                cred_dict['private_key'] = private_key.replace('\\n', '\n')

            cred = credentials.Certificate(cred_dict)
            print('Firebase Admin SDK inicializado desde variable de entorno JSON')
        else:
            cred_path = Path(firebase_creds)
            if not cred_path.is_absolute():
                cred_path = base_dir / cred_path

            if not cred_path.exists():
                print(f'Firebase no inicializado: no existe el archivo de credenciales en {cred_path}')
                return

            cred = credentials.Certificate(str(cred_path))
            print(f'Firebase Admin SDK inicializado desde archivo: {cred_path}')

        firebase_admin.initialize_app(cred)
    except Exception as exc:
        print(f'Error inicializando Firebase: {exc}')
