from __future__ import annotations

import re
from typing import Any

from app.services.normalization.common import _clean_text

SIDO_ALIASES = {
    "서울": "서울특별시",
    "서울특별시": "서울특별시",
    "부산": "부산광역시",
    "부산광역시": "부산광역시",
    "대구": "대구광역시",
    "대구광역시": "대구광역시",
    "인천": "인천광역시",
    "인천광역시": "인천광역시",
    "광주": "광주광역시",
    "광주광역시": "광주광역시",
    "대전": "대전광역시",
    "대전광역시": "대전광역시",
    "울산": "울산광역시",
    "울산광역시": "울산광역시",
    "세종": "세종특별자치시",
    "세종특별자치시": "세종특별자치시",
    "경기": "경기도",
    "경기도": "경기도",
    "강원": "강원특별자치도",
    "강원도": "강원특별자치도",
    "강원특별자치도": "강원특별자치도",
    "충북": "충청북도",
    "충청북도": "충청북도",
    "충남": "충청남도",
    "충청남도": "충청남도",
    "전북": "전북특별자치도",
    "전라북도": "전북특별자치도",
    "전북특별자치도": "전북특별자치도",
    "전남": "전라남도",
    "전라남도": "전라남도",
    "경북": "경상북도",
    "경상북도": "경상북도",
    "경남": "경상남도",
    "경상남도": "경상남도",
    "제주": "제주특별자치도",
    "제주도": "제주특별자치도",
    "제주특별자치도": "제주특별자치도",
}

SIGUNGU_TO_SIDO = {
    "수원": "경기도", "성남": "경기도", "의정부": "경기도", "안양": "경기도", "부천": "경기도",
    "광명": "경기도", "평택": "경기도", "동두천": "경기도", "안산": "경기도", "고양": "경기도",
    "과천": "경기도", "구리": "경기도", "남양주": "경기도", "오산": "경기도", "시흥": "경기도",
    "군포": "경기도", "의왕": "경기도", "하남": "경기도", "용인": "경기도", "파주": "경기도",
    "이천": "경기도", "안성": "경기도", "김포": "경기도", "화성": "경기도", "양주": "경기도",
    "포천": "경기도", "여주": "경기도", "연천": "경기도", "가평": "경기도", "양평": "경기도",
    "동탄": "경기도",
    "춘천": "강원특별자치도", "원주": "강원특별자치도", "강릉": "강원특별자치도", "동해": "강원특별자치도",
    "태백": "강원특별자치도", "속초": "강원특별자치도", "삼척": "강원특별자치도", "홍천": "강원특별자치도",
    "횡성": "강원특별자치도", "영월": "강원특별자치도", "평창": "강원특별자치도", "정선": "강원특별자치도",
    "철원": "강원특별자치도", "화천": "강원특별자치도", "양구": "강원특별자치도", "인제": "강원특별자치도",
    "고성": "강원특별자치도", "양양": "강원특별자치도",
    "청주": "충청북도", "충주": "충청북도", "제천": "충청북도", "보은": "충청북도", "옥천": "충청북도",
    "영동": "충청북도", "증평": "충청북도", "진천": "충청북도", "괴산": "충청북도", "음성": "충청북도",
    "단양": "충청북도",
    "천안": "충청남도", "공주": "충청남도", "보령": "충청남도", "아산": "충청남도", "서산": "충청남도",
    "논산": "충청남도", "계룡": "충청남도", "당진": "충청남도", "금산": "충청남도", "부여": "충청남도",
    "서천": "충청남도", "청양": "충청남도", "홍성": "충청남도", "예산": "충청남도", "태안": "충청남도",
    "전주": "전북특별자치도", "군산": "전북특별자치도", "익산": "전북특별자치도", "정읍": "전북특별자치도",
    "남원": "전북특별자치도", "김제": "전북특별자치도", "완주": "전북특별자치도", "진안": "전북특별자치도",
    "무주": "전북특별자치도", "장수": "전북특별자치도", "임실": "전북특별자치도", "순창": "전북특별자치도",
    "고창": "전북특별자치도", "부안": "전북특별자치도",
    "목포": "전라남도", "여수": "전라남도", "순천": "전라남도", "나주": "전라남도", "광양": "전라남도",
    "담양": "전라남도", "곡성": "전라남도", "구례": "전라남도", "고흥": "전라남도", "보성": "전라남도",
    "화순": "전라남도", "장흥": "전라남도", "강진": "전라남도", "해남": "전라남도", "영암": "전라남도",
    "무안": "전라남도", "함평": "전라남도", "영광": "전라남도", "장성": "전라남도", "완도": "전라남도",
    "진도": "전라남도", "신안": "전라남도",
    "포항": "경상북도", "경주": "경상북도", "김천": "경상북도", "안동": "경상북도", "구미": "경상북도",
    "영주": "경상북도", "영천": "경상북도", "상주": "경상북도", "문경": "경상북도", "경산": "경상북도",
    "군위": "대구광역시", "의성": "경상북도", "청송": "경상북도", "영양": "경상북도", "영덕": "경상북도",
    "청도": "경상북도", "고령": "경상북도", "성주": "경상북도", "칠곡": "경상북도", "예천": "경상북도",
    "봉화": "경상북도", "울진": "경상북도", "울릉": "경상북도",
    "창원": "경상남도", "진주": "경상남도", "통영": "경상남도", "사천": "경상남도", "김해": "경상남도",
    "밀양": "경상남도", "거제": "경상남도", "양산": "경상남도", "의령": "경상남도", "함안": "경상남도",
    "창녕": "경상남도", "고성": "경상남도", "남해": "경상남도", "하동": "경상남도", "산청": "경상남도",
    "함양": "경상남도", "거창": "경상남도", "합천": "경상남도",
    "서귀포": "제주특별자치도", "제주": "제주특별자치도",
    # 광역시의 고유 구·군. 중구/서구/동구/남구/북구처럼 여러 시에
    # 중복되는 이름은 상위 시·도 없이 확정할 수 없어 의도적으로 제외한다.
    "종로": "서울특별시", "용산": "서울특별시", "성동": "서울특별시", "광진": "서울특별시",
    "동대문": "서울특별시", "중랑": "서울특별시", "성북": "서울특별시", "강북": "서울특별시",
    "도봉": "서울특별시", "노원": "서울특별시", "은평": "서울특별시", "서대문": "서울특별시",
    "마포": "서울특별시", "양천": "서울특별시", "구로": "서울특별시", "금천": "서울특별시",
    "영등포": "서울특별시", "동작": "서울특별시", "관악": "서울특별시", "서초": "서울특별시",
    "강남": "서울특별시", "송파": "서울특별시", "강동": "서울특별시",
    "해운대": "부산광역시", "수영": "부산광역시", "사상": "부산광역시", "연제": "부산광역시",
    "금정": "부산광역시", "기장": "부산광역시", "달서": "대구광역시", "달성": "대구광역시",
    "수성": "대구광역시", "계양": "인천광역시", "미추홀": "인천광역시", "연수": "인천광역시",
    "부평": "인천광역시", "강화": "인천광역시", "옹진": "인천광역시", "유성": "대전광역시",
    "대덕": "대전광역시", "광산": "광주광역시", "울주": "울산광역시"
}

REGION_GROUPS = {
    "수도권": ["서울특별시", "인천광역시", "경기도"],
    "충청권": ["대전광역시", "세종특별자치시", "충청북도", "충청남도"],
    "충청호남권": ["대전광역시", "세종특별자치시", "충청북도", "충청남도", "광주광역시", "전북특별자치도", "전라남도"],
    "호남권": ["광주광역시", "전북특별자치도", "전라남도"],
    "영남권": ["부산광역시", "대구광역시", "울산광역시", "경상북도", "경상남도"],
    "동남권": ["부산광역시", "울산광역시", "경상남도"],
    "대경권": ["대구광역시", "경상북도"],
    "강원권": ["강원특별자치도"],
    "제주권": ["제주특별자치도"],
}


def _extract_region_metadata(
    value: str | None,
    default_scope: str = "unknown",
    *,
    fallback_text: str | None = None,
    supporting_text: str | None = None,
) -> dict[str, Any]:
    primary = _match_region_text(value, allow_bare_sigungu=False)
    fallback = _match_region_text(fallback_text, allow_bare_sigungu=True)
    supporting = _match_region_text(supporting_text, allow_bare_sigungu=True)
    if primary["matched_sidos"]:
        # 지원대상 본문이 광역 시·도만 말하고 기관명이 더 구체적인 시·군·구를
        # 담는 경우가 많다. 예: 대상="경기도 소상공인", 기관="경기도 의왕시".
        # 명시된 광역권이 같은 경우에만 기관 근거로 보강해 타 시·군 정책이
        # 같은 시·도 전체 정책으로 넓어지는 것을 막는다.
        if (
            supporting["matched_sidos"]
            and set(primary["matched_sidos"]) & set(supporting["matched_sidos"])
        ):
            combined = _combine_region_matches(primary, supporting)
            return _region_result(
                combined,
                region_scope="local",
                condition_mode="restricted",
                confidence=0.95,
                extraction_method="eligibility_and_organization_region_rule",
                source_ref="eligibility+organization",
            )
        return _region_result(
            primary,
            region_scope="local",
            condition_mode="restricted",
            confidence=0.93,
            extraction_method="eligibility_region_rule",
            source_ref="eligibility",
        )
    if primary["is_national"]:
        return _region_result(
            primary,
            region_scope="national",
            condition_mode="unrestricted",
            confidence=0.96,
            extraction_method="eligibility_region_rule",
            source_ref="eligibility",
        )

    if fallback["matched_sidos"] and supporting["matched_sidos"]:
        shared_sidos = set(fallback["matched_sidos"]) & set(supporting["matched_sidos"])
        if shared_sidos:
            combined = _combine_region_matches(fallback, supporting)
            return _region_result(
                combined,
                region_scope="local",
                condition_mode="restricted",
                confidence=0.92,
                extraction_method="title_and_organization_region_rule",
                source_ref="title+organization",
            )
        combined = _combine_region_matches(fallback, supporting)
        return _region_result(
            combined,
            region_scope="local",
            condition_mode="unknown",
            confidence=0.45,
            extraction_method="conflicting_title_organization_region_rule",
            source_ref="title+organization_conflict",
        )

    if fallback["matched_sidos"]:
        # 제목에 시·군·구가 있고 지원대상 본문이 "관내 사업자"처럼 지역
        # 제한을 명시하면, 제목은 단순 행사 장소가 아니라 그 "관내"가 가리키는
        # 실제 신청 지역이다. 실제 데이터의 "시흥시 ... 지원" + "관내 2개월
        # 이상 운영" 같은 공고를 다른 시 사용자에게 추천하지 않도록 신뢰도를
        # 높인다. 제목에만 지역이 있는 경우에는 기존의 낮은 신뢰도를 유지한다.
        scoped_by_primary_text = _has_local_scope_marker(value)
        explicit_leading_region = _has_explicit_leading_region(fallback_text, fallback)
        return _region_result(
            fallback,
            region_scope="local",
            condition_mode="restricted",
            confidence=(
                0.9
                if explicit_leading_region
                else 0.88
                if scoped_by_primary_text
                else 0.68
            ),
            extraction_method=(
                "explicit_title_region_rule"
                if explicit_leading_region
                else "title_region_with_eligibility_scope_rule"
                if scoped_by_primary_text
                else "title_region_rule"
            ),
            source_ref=(
                "title"
                if explicit_leading_region
                else "title+eligibility"
                if scoped_by_primary_text
                else "title"
            ),
        )
    if fallback["is_national"]:
        return _region_result(
            fallback,
            region_scope="national",
            condition_mode="unrestricted",
            confidence=0.82,
            extraction_method="title_region_rule",
            source_ref="title",
        )

    if supporting["matched_sidos"]:
        scoped_by_primary_text = _has_local_scope_marker(value)
        return _region_result(
            supporting,
            region_scope="local",
            condition_mode="restricted",
            confidence=0.88 if scoped_by_primary_text else 0.82,
            extraction_method=(
                "organization_region_with_eligibility_scope_rule"
                if scoped_by_primary_text
                else "organization_region_rule"
            ),
            source_ref=(
                "organization+eligibility"
                if scoped_by_primary_text
                else "organization"
            ),
        )

    return {
        "region_scope": default_scope,
        "condition_mode": "unknown",
        "sido": None,
        "sigungu": None,
        "matched_sidos": [],
        "confidence": 0.55 if default_scope != "unknown" else 0.2,
        "extraction_method": "source_default" if default_scope != "unknown" else "rule",
        "source_ref": "source_default" if default_scope != "unknown" else None,
        "evidence": [],
    }


def _match_region_text(value: str | None, *, allow_bare_sigungu: bool) -> dict[str, Any]:
    text_value = _clean_text(value) or ""
    matched_sidos: list[str] = []
    evidence: list[str] = []
    for alias, sido in sorted(SIDO_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if _contains_region_alias(
            text_value,
            alias,
            allow_organization_suffix=allow_bare_sigungu,
        ) and sido not in matched_sidos:
            matched_sidos.append(sido)
            evidence.append(alias)
    for group_name, sidos in REGION_GROUPS.items():
        if group_name not in text_value:
            continue
        evidence.append(group_name)
        for sido in sidos:
            if sido not in matched_sidos:
                matched_sidos.append(sido)

    sigungu_val = None
    if not matched_sidos:
        for sigungu, sido in SIGUNGU_TO_SIDO.items():
            if allow_bare_sigungu:
                pattern = rf"(?<![가-힣]){re.escape(sigungu)}(?:시|군|구)?(?![가-힣])"
            else:
                pattern = (
                    rf"(?<![가-힣]){re.escape(sigungu)}(?:시|군|구)"
                    rf"(?=$|\s|[,.()\[\]]|에|에서|의|내|로|소재|거주)"
                )
            match = re.search(pattern, text_value)
            if match is None and allow_bare_sigungu:
                brand_pattern = (
                    rf"(?<![가-힣]){re.escape(sigungu)}"
                    rf"(?=(?:사랑상품권|사랑카드|지역화폐|페이))"
                )
                match = re.search(brand_pattern, text_value)
            if match:
                if sido not in matched_sidos:
                    matched_sidos.append(sido)
                sigungu_val = match.group(0)
                evidence.append(sigungu_val)
                break

    is_national = any(token in text_value for token in ("전국", "전 지역", "전국민", "전국 단위"))
    if sigungu_val is None:
        sigungu = _extract_sigungu_after_sido(text_value, matched_sidos) if matched_sidos else None
    else:
        sigungu = sigungu_val
    return {
        "matched_sidos": matched_sidos,
        "sigungu": sigungu,
        "is_national": is_national,
        "evidence": evidence + (["전국"] if is_national else []),
    }


def _region_result(
    match: dict[str, Any],
    *,
    region_scope: str,
    condition_mode: str,
    confidence: float,
    extraction_method: str,
    source_ref: str,
) -> dict[str, Any]:
    matched_sidos = match["matched_sidos"]
    return {
        "region_scope": region_scope,
        "condition_mode": condition_mode,
        "sido": matched_sidos[0] if matched_sidos else None,
        "sigungu": match["sigungu"],
        "matched_sidos": matched_sidos,
        "confidence": confidence,
        "extraction_method": extraction_method,
        "source_ref": source_ref,
        "evidence": match["evidence"],
    }


def _combine_region_matches(
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    matched_sidos = list(dict.fromkeys(left["matched_sidos"] + right["matched_sidos"]))
    return {
        "matched_sidos": matched_sidos,
        "sigungu": left.get("sigungu") or right.get("sigungu"),
        "is_national": bool(left.get("is_national") or right.get("is_national")),
        "evidence": list(dict.fromkeys((left.get("evidence") or []) + (right.get("evidence") or []))),
    }


def _contains_region_alias(
    text_value: str,
    alias: str,
    *,
    allow_organization_suffix: bool = False,
) -> bool:
    if len(alias) >= 4 or alias.endswith(("특별시", "광역시", "특별자치시", "특별자치도", "도")):
        return alias in text_value
    if re.search(rf"(?<![가-힣]){re.escape(alias)}(?:시|도)?(?![가-힣])", text_value):
        return True
    if not allow_organization_suffix:
        return False
    # 기관명에서는 충북신용보증재단처럼 축약 시·도명 뒤에 바로 기관명이
    # 붙는다. 임의의 단어 내부 매칭은 허용하지 않고 지역 공공기관의 대표
    # 접미사만 화이트리스트로 인정한다.
    return bool(
        re.search(
            rf"(?<![가-힣]){re.escape(alias)}"
            r"(?=(?:신용보증재단|경제진흥원|시장상권진흥원|테크노파크|"
            r"창조경제혁신센터|상공회의소))",
            text_value,
        )
    )


def _has_local_scope_marker(value: str | None) -> bool:
    text_value = _clean_text(value) or ""
    return bool(
        re.search(
            r"(?:관내|도내|시내|군내|구내|해당\s*지역\s*내|지역\s*내|"
            r"사업장(?:을|이|가)?\s*(?:둔|소재)|주소지(?:를|가)?\s*(?:둔|소재))",
            text_value,
        )
    )


def _has_explicit_leading_region(value: str | None, match: dict[str, Any]) -> bool:
    """Return true when a title begins with a full official 시·도 name."""

    text_value = (_clean_text(value) or "").lstrip("[（(")
    full_names = {
        alias
        for alias, sido in SIDO_ALIASES.items()
        if sido in match["matched_sidos"] and alias == sido
    }
    return any(text_value.startswith(name) for name in full_names)


def _extract_sigungu_after_sido(text_value: str, matched_sidos: list[str]) -> str | None:
    aliases = [
        alias
        for alias, sido in SIDO_ALIASES.items()
        if sido in matched_sidos
    ]
    bad_tokens = (
        "시군구",
        "시도",
        "소상공인시",
        "소상공인시장",
        "중소기업",
        "고용시",
        "산업구",
        "전시",
    )
    for alias in sorted(aliases, key=len, reverse=True):
        pattern = re.compile(rf"{re.escape(alias)}\s+([가-힣]{{2,6}}(?:시|군|구))")
        match = pattern.search(text_value)
        if not match:
            continue
        token = match.group(1)
        if token in SIDO_ALIASES.values() or any(bad in token for bad in bad_tokens):
            continue
        return token
    return None
