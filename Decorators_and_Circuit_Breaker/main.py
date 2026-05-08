from functools import wraps
import time
from collections import deque

class NotAliveError(Exception):
    pass

def circuit_breaker(state_count, error_count, network_errors, sleep_time_sec):
    if (state_count <= 10):
        raise ValueError("state count must be > 10")
    if (error_count >= 10):
        raise ValueError("error count must be < 10")

    def decorator(func):
        last_failure_time = 0
        state = 'CLOSED'
        history = deque(maxlen=state_count)
        errors_tuple = tuple(network_errors)
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal state, last_failure_time, history
            timestamp = time.time()
            if state == 'OPEN':
                if (timestamp - last_failure_time >= sleep_time_sec):
                    state = 'HALF_OPEN'
                else:
                    raise NotAliveError("Circuit breaker is OPEN. Operation not allowed.")

            if state == 'CLOSED':
                if len(history) >= error_count and all(x is False for x in list(history)[-error_count:]):
                    state = 'OPEN'
                    last_failure_time = timestamp
                    raise NotAliveError("Service unavailable: too many consecutive failures")

            if state != 'OPEN' and history[-1] is False:
                time.sleep(sleep_time_sec)

            try:
                result = func(*args, **kwargs)
            except errors_tuple as e:
                history.append(False)
                last_failure_time = time.time()
                if state == 'HALF_OPEN':
                    state = 'OPEN'
                else:
                    if sum(1 for x in history if x is False) >= error_count:
                        state = 'OPEN'
                raise
            else:
                history.append(True)
                if state == 'HALF_OPEN':
                    state = 'CLOSED'
                    history.clear()
                return result
        return wrapper
    return decorator
