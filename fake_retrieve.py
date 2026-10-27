"""
Fake retrieve() so the pipeline can be built before Mayssa's real index is ready.
It returns chunks in the same format we agreed on: {id, text, title, section, url} + score.
When the real retrieve() is ready, we just swap the import.
"""

FAKE_CHUNKS = [
    {
        "id": "sc-1.4.3",
        "text": "Success Criterion 1.4.3 Contrast (Minimum) (Level AA): The visual presentation "
                "of text and images of text has a contrast ratio of at least 4.5:1. Large text "
                "(at least 18 point, or 14 point bold) needs a contrast ratio of at least 3:1.",
        "title": "Contrast (Minimum)",
        "section": "1.4.3",
        "url": "https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html",
    },
    {
        "id": "sc-2.5.8",
        "text": "Success Criterion 2.5.8 Target Size (Minimum) (Level AA): The size of the target "
                "for pointer inputs is at least 24 by 24 CSS pixels, except when there is enough "
                "spacing around it, an equivalent control exists, the target is inline in text, "
                "its size is set by the browser, or a specific size is essential.",
        "title": "Target Size (Minimum)",
        "section": "2.5.8",
        "url": "https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html",
    },
    {
        "id": "sc-1.1.1",
        "text": "Success Criterion 1.1.1 Non-text Content (Level A): All non-text content presented "
                "to the user has a text alternative that serves the equivalent purpose. A button "
                "that shows only an icon must have a text alternative (an accessible name) "
                "describing what the button does.",
        "title": "Non-text Content",
        "section": "1.1.1",
        "url": "https://www.w3.org/WAI/WCAG22/Understanding/non-text-content.html",
    },
]


def retrieve(query, k=5):
    """Return up to k chunks, best first. Score = how many query words appear in the chunk."""
    words = query.lower().split()
    results = []
    for chunk in FAKE_CHUNKS:
        text = chunk["text"].lower()
        score = sum(1 for w in words if w in text)
        results.append({**chunk, "score": score})
    results.sort(key=lambda c: c["score"], reverse=True)
    return results[:k]


if __name__ == "__main__":
    for c in retrieve("how big should a button be"):
        print(c["score"], c["section"], c["title"])