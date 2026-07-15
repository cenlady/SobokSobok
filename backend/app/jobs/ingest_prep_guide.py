# -*- coding: utf-8 -*-
"""이전 Prep 적재 명령의 호환 진입점.

과거에는 policy_documents의 일정 단락으로 prep_vectors를 덮어썼다. 현재 prep_vectors는
서류 발급 가이드 전용이므로 canonical job으로 위임한다.
"""

from app.jobs.build_prep_vectors_once import build_prep_vectors_once


def build_prep_vectors() -> dict[str, int | str]:
    return build_prep_vectors_once()


if __name__ == "__main__":
    result = build_prep_vectors()
    print(
        f"[prep-vectors] 가이드 {result['guides']}개 → {result['written']}건 적재",
        flush=True,
    )
