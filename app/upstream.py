"""Bounded retries and safe public errors; never expose provider response bodies."""
import time
import random
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import httpx


class ProviderError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def public_error(exc):
    if isinstance(exc, httpx.TimeoutException):
        return ProviderError(504, '模型服务响应超时，请稍后重试。')
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return ProviderError(502, '模型服务鉴权失败，请检查对应平台的 API Key 和模型权限。')
        if code == 402:
            return ProviderError(502, '模型账户余额不足，请检查对应平台余额。')
        if code == 429:
            return ProviderError(503, '模型服务请求过于频繁或额度受限，请稍后重试并检查配额。')
        if code in (400, 404, 422):
            return ProviderError(502, '模型服务不接受当前配置，请检查接口地址、模型名称和参数。')
    return ProviderError(502, '模型服务连接失败或返回异常，请稍后重试。')


def retry_delay(exc, attempt, cap):
    delay = min(cap, 0.5 * 2**attempt + random.uniform(0, .25))
    if isinstance(exc, httpx.HTTPStatusError):
        header = exc.response.headers.get('Retry-After')
        if header:
            try:
                requested = float(header)
            except ValueError:
                try:
                    requested = (parsedate_to_datetime(header)-datetime.now(timezone.utc)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    return delay
            # If the provider asks for a longer wait, fail rather than retry early.
            if requested > cap:
                return None
            delay = max(delay, max(0, requested))
    return delay


class Transport:
    def __init__(self, settings):
        self.s = settings

    @contextmanager
    def stream(self, base, key, path, body):
        if not base or not key:
            raise ProviderError(503, '尚未配置模型服务地址或 API Key，请检查 .env。')
        timeout = httpx.Timeout(self.s.model_timeout_seconds, connect=self.s.model_connect_timeout_seconds)
        with httpx.Client(timeout=timeout) as client:
            for attempt in range(self.s.model_max_retries+1):
                response = None
                try:
                    request = client.build_request('POST', base.rstrip('/')+path,
                        headers={'Authorization': f'Bearer {key}'}, json=body)
                    response = client.send(request, stream=True)
                    response.raise_for_status()
                except (httpx.HTTPError, ValueError) as exc:
                    if response is not None:
                        response.close()
                    retryable = isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)) or (
                        isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (429, 502, 503, 504))
                    delay = retry_delay(exc, attempt, self.s.model_retry_max_delay_seconds)
                    if not retryable or attempt == self.s.model_max_retries or delay is None:
                        raise public_error(exc) from exc
                    time.sleep(delay)
                    continue
                try:
                    # No retries after headers: avoid replaying partial generations
                    # or paid requests with ambiguous outcomes.
                    yield response
                except httpx.HTTPError as exc:
                    raise public_error(exc) from exc
                finally:
                    response.close()
                break

    def post(self, base, key, path, body):
        with self.stream(base,key,path,body) as response:
            response.read()
            try:
                return response.json()
            except ValueError as exc:
                raise ProviderError(502, '模型服务返回了无法解析的数据，请稍后重试。') from exc
