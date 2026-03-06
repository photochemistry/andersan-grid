from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional

import requests


# ai-docs 自体が http:// で提供されているため、実際のエンドポイントも http をデフォルトとする
DEFAULT_BASE_URL = "http://andersan.net:8089"


class AirPollutionWatchClient:
    """
    airpollutionwatch API 用の薄いクライアント.

    主に /v1/stations と /v1/measurements (format=snapshot) を利用する。
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        env_url = os.getenv("AIRPOLLUTIONWATCH_BASE_URL")
        self.base_url = (base_url or env_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    def _get(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = self._session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_stations(self, pref: str = None) -> List[Dict[str, Any]]:
        """
        指定した都道府県の局メタデータ一覧を取得する.
        """
        if pref is None or pref.lower() == "japan":
            data = self._get("/v1/stations", params={})
        else:
            data = self._get("/v1/stations", params={"pref": pref})
        # Swagger の詳細が手元にないため、典型的な形を想定:
        # { "stations": [ {...}, ... ] } または単純な配列
        return data

    def get_snapshot_measurements(
        self,
        pref: str,
        target_datetime: str,
        pollutants: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        /v1/measurements を format=snapshot で叩き、1 時刻の局ごとの観測値一覧を取得する.

        target_datetime は ISO8601 文字列（例: 2024-09-03T06:00:00+09:00）を想定する。
        """
        params: Dict[str, Any] = {
            "pref": pref,
            "from": target_datetime,
            "to": target_datetime,
            "format": "snapshot",
        }
        if pollutants:
            params["pollutants"] = ",".join(pollutants)

        data = self._get("/v1/measurements", params=params)

        # docs/measurements-response-formats.md を見られないため、
        # よくあるパターンを柔軟にハンドリングする。
        if isinstance(data, list):
            return data
        for key in ("records", "stations", "items", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
        raise ValueError("Unexpected /v1/measurements snapshot response format")
