from dataclasses import dataclass
from datetime import datetime as dt
import json

from pathlib import Path
import re


@dataclass(frozen=True)
class LogEvent:
    service_name: str
    event_type: str
    datetime: dt
    message: str


class LogReader:
    def __init__(self, log_dir: str | Path) -> None:
        self._log_dir = Path(log_dir)
        if not self._log_dir.exists():
            raise FileNotFoundError(f"Directory does not exist: {self._log_dir}")
        if not self._log_dir.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self._log_dir}")

    _FILE_RE = re.compile(
        r"^(?P<service>.+)_(?P<hour>\d{10})\.log$"
    )

    def _parse_filename(self, path: Path) -> tuple[str, dt]:
        match = self._FILE_RE.match(path.name)

        if match is None:
            raise ValueError(f"Invalid log filename: {path.name}")
        service_name = match.group("service")
        hour_str = match.group("hour")

        try:
            hour_dt = dt.strptime(hour_str, "%Y%m%d%H")
        except ValueError as exc:
            raise ValueError(f"Invalid date in filename: {path.name}") from exc
        return service_name, hour_dt

    def _get_service_files(self, service_name: str) -> list[Path]:
        result: list[Path] = []

        for path in self._log_dir.iterdir():
            if not path.is_file():
                continue
            match = self._FILE_RE.match(path.name)
            if match is None:
                continue
            current_service = match.group("service")
            if current_service != service_name:
                continue
            result.append(path)
        result.sort(key=lambda p: self._parse_filename(p)[1])
        return result

    def _parse_file(self, path: Path) -> list[LogEvent]:
        service_name, expected_hour = self._parse_filename(path)
        events: list[LogEvent] = []

        with path.open("r", encoding="utf-8", newline="\n") as file:
            for line_number, raw_line in enumerate(file, start=1):
                line = raw_line.rstrip("\n")
                if not line:
                    continue

                payload = json.loads(line)
        try:
            event_dt_raw = payload["datetime"]
            event_type = payload["event_type"]
            message_template = payload["message"]
            params = payload["params"]
        except KeyError as exc:
            raise ValueError(
                f"Missing required field {exc.args[0]!r} in {path.name} at line {line_number}"
            ) from exc

        if not isinstance(params, dict):
            raise ValueError(
                f"'params' must be a dict in {path.name} at line {line_number}"
            )

        try:
            event_dt = dt.fromisoformat(event_dt_raw)
        except ValueError as exc:
            raise ValueError(
                f"Invalid datetime format in {path.name} at line {line_number}"
            ) from exc

        if event_type not in {"ERROR", "INFO", "DEBUG"}:
            raise ValueError(
                f"Invalid event_type {event_type!r} in {path.name} at line {line_number}"
            )

        try:
            message = message_template.format(**params)
        except KeyError as exc:
            raise ValueError(
                f"Missing interpolation parameter {exc.args[0]!r} in {path.name} at line {line_number}"
            ) from exc

        events.append(
            LogEvent(
                service_name=service_name,
                datetime=event_dt,
                event_type=event_type,
                message=message,
            )
        )
        return events

    def get_last_events(self, service_name: str, limit: int) -> list[LogEvent]:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        service_files = self._get_service_files(service_name)
        if not service_files:
            raise ValueError(f"Unknown service: {service_name}")

        result: list[LogEvent] = []

        for path in reversed(service_files):
            events = self._parse_file(path)

            for event in reversed(events):
                result.append(event)
                if len(result) == limit:
                    result.reverse()
                    return result

        result.reverse()
        return result