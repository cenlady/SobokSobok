// 공고 원문을 화면에 얹기 전에 다듬는다.
//
// 크롤링한 원문은 PDF·HWP에서 뽑아낸 것이라 줄바꿈이 문장 중간에서 끊기고, 빈 줄이
// 서너 개씩 이어지고, 장식용 구분선(----, ○○○)이 섞여 있다. 이걸 whitespace-pre-line으로
// 그대로 뿌리면 읽기가 매우 어렵다.

/** 장식용 구분선. 정보가 없으므로 지운다. */
const SEPARATOR = /^[\s\-=_·※○●▶▷□■◆◇*~]{3,}$/

export function cleanPolicyText(raw?: string | null): string {
  if (!raw) return ''

  const lines = raw
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map((line) => line.replace(/[ \t]+/g, ' ').trim())
    .filter((line) => !SEPARATOR.test(line))

  const merged: string[] = []
  for (const line of lines) {
    if (!line) {
      // 빈 줄이 여러 개 이어져도 문단 구분 하나로만 친다.
      if (merged.length && merged[merged.length - 1] !== '') merged.push('')
      continue
    }

    const prev = merged[merged.length - 1]
    // 앞 줄이 문장 부호로 끝나지 않고, 이 줄이 항목 기호로 시작하지 않으면
    // PDF 추출 과정에서 한 문장이 잘린 것으로 보고 이어 붙인다.
    const isContinuation =
      prev &&
      prev !== '' &&
      !/[.!?:;。]$/.test(prev) &&
      !/^[-•·▪‣◦\d]|^[가-힣]\)|^\(/.test(line)

    if (isContinuation) {
      merged[merged.length - 1] = `${prev} ${line}`
    } else {
      merged.push(line)
    }
  }

  return merged.join('\n').replace(/\n{3,}/g, '\n\n').trim()
}

/** 긴 본문을 접어 보여줄 때 쓸 앞부분. 문장 경계에서 자른다. */
export function truncateAtSentence(text: string, limit = 180): string {
  if (text.length <= limit) return text

  const head = text.slice(0, limit)
  const lastStop = Math.max(head.lastIndexOf('. '), head.lastIndexOf('\n'), head.lastIndexOf('다.'))

  return lastStop > limit * 0.5 ? head.slice(0, lastStop + 1).trim() : `${head.trim()}…`
}
