from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError


class ExaLookupTimeout(Exception):
    pass


class ExaSearch:
    """Search adapter. The policy never imports or invokes it directly."""

    def __init__(self, api_key: str | None = None) -> None:
        from exa_py import Exa

        self.client = Exa(api_key=api_key or os.environ["EXA_API_KEY"])

    def answer(self, query: str) -> str:
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="exa-lookup")
        future = executor.submit(self.client.search, query, num_results=3, contents={"highlights": True})
        try:
            response = future.result(timeout=int(os.getenv("EXA_TIMEOUT_SECONDS", "25")))
        except TimeoutError as error:
            future.cancel()
            raise ExaLookupTimeout("Exa did not return within the lookup timeout") from error
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        results = response.results
        if not results:
            return "I couldn't find a useful result for that."
        lines = []
        for result in results:
            highlight = (result.highlights or [""])[0].replace("\n", " ")[:280]
            lines.append(f"• <{result.url}|{result.title}>" + (f" — {highlight}" if highlight else ""))
        return "Here’s what I found:\n" + "\n".join(lines)


def mention_query(text: str) -> str:
    return re.sub(r"<@[^>]+>", "", text).strip()
