from dataclasses import dataclass
from datetime import datetime as dt
import json
import heapq

from pathlib import Path
import re

@dataclass(frozen=True)
class LogEvent:
    service_name: str
    event_type: str
    datetime: dt
    message: str
    params: dict[str, str]

class LogReader:
    def __init__(self, log_dir: str | Path) -> None:
        self._error_cache: dict[Path, list[dt]] = {}
        self._log_dir = Path(log_dir)
        if not self._log_dir.exists():
            raise FileNotFoundError(f"Directory does not exist: {self._log_dir}")
        if not self._log_dir.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self._log_dir}")

    _FILE_RE = re.compile(
        r"^(?P<service>.+)_(?P<hour>\d{10})\.log$"
    )

    def _get_file_errors(self, path: Path) -> list[dt]:
        if path in self._error_cache:
            return self._error_cache[path]
        errors: list[dt] = []

        events = self._parse_file(path)
        for event in events:
            if event.event_type == "ERROR":
                errors.append(event.datetime)

        self._error_cache[path] = errors
        return errors

    def get_error_counts(
            self,
            start: dt,
            end: dt
    ) -> dict[str, int]:
        if start > end:
            raise ValueError("start must be <= end")
        result: dict[str, int] = {}
        for path in self._get_all_log_files():
            service_name, _ = self._parse_filename(path)
            error_times = self._get_file_errors(path)
            count = 0
            for error_dt in error_times:
                if start <= error_dt <= end:
                    count += 1
            result[service_name] = result.get(service_name, 0) + count

        return result

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
                        params=params,
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

    def _get_all_log_files(self) -> list[Path]:
        result = []
        for path in self._log_dir.iterdir():
            if not path.is_file():
                continue
            if self._FILE_RE.match(path.name) is None:
                continue
            result.append(path)
        return result

    def get_last_events_all(self, n: int) -> list[LogEvent]:
        if n <= 0:
            raise ValueError("n must be positive")

        files = self._get_all_log_files()

        parsed_files: list[list[LogEvent]] = []

        for path in files:
            events = self._parse_file(path)
            if events:
                parsed_files.append(events)

        heap: list[tuple[float, int, int]] = []

        for file_index, events in enumerate(parsed_files):
            last_index = len(events) - 1
            event = events[last_index]

            heapq.heappush(
                heap,
                (-event.datetime.timestamp(), file_index, last_index)
            )

        result: list[LogEvent] = []

        while heap and len(result) < n:
            _, file_index, event_index = heapq.heappop(heap)
            event = parsed_files[file_index][event_index]
            result.append(event)
            prev_index = event_index - 1
            if prev_index >= 0:
                prev_event = parsed_files[file_index][prev_index]
                heapq.heappush(
                    heap,
                    (-prev_event.datetime.timestamp(), file_index, prev_index)
                )
        result.reverse()
        return result

    def get_last_events_all_with_object(
            self,
            n: int,
            object_value: str
    ) -> list[LogEvent]:
        if n <= 0:
            raise ValueError("n must be positive")

        files = self._get_all_log_files()
        parsed_files: list[list[LogEvent]] = []

        for path in files:
            events = [
                event
                for event in self._parse_file(path)
                if object_value in event.params.values()
            ]
            if events:
                parsed_files.append(events)
        heap: list[tuple[float, int, int]] = []

        for file_index, events in enumerate(parsed_files):
            last_index = len(events) - 1
            event = events[last_index]

            heapq.heappush(
                heap,
                (-event.datetime.timestamp(), file_index, last_index)
            )
        result: list[LogEvent] = []
        while heap and len(result) < n:
            _, file_index, event_index = heapq.heappop(heap)
            event = parsed_files[file_index][event_index]
            result.append(event)
            prev_index = event_index - 1

            if prev_index >= 0:
                prev_event = parsed_files[file_index][prev_index]

                heapq.heappush(
                    heap,
                    (-prev_event.datetime.timestamp(), file_index, prev_index)
                )
        result.reverse()
        return result

import sys
import sysconfig
def detect_python_build():
    # Проверяем тип сборки
    gil_disabled = sysconfig.get_config_var("Py_GIL_DISABLED")
    if gil_disabled:
        build_type = "Free-Threading Build"
    else:
        build_type = "Standard Build"
        #Проверяем статус GIL в рантайме (Python 3.13+)
    gil_status = "Unknown"
    if hasattr(sys, "_is_gil_enabled"):
        gil_enabled = sys._is_gil_enabled()
        gil_status = "ON" if gil_enabled else "OFF"
    else:
        gil_status = "N/A (Python < 3.13)"
    return build_type, gil_status
build_type, gil_status = detect_python_build()


print("Тип сборки:", build_type)
print("Статус GIL:", gil_status)