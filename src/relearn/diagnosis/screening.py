import re

from relearn.schemas import LearnerResponse, Question

NON_ANSWERS = {
    "idk",
    "i dont know",
    "dont know",
    "dunno",
    "no idea",
    "not sure",
    "im not sure",
    "no clue",
    "pass",
    "skip",
    "na",
    "n a",
    "nothing",
    "none",
    "whatever",
    "",
}
MIN_REASONING_WORDS = 3
NON_WORD = re.compile(r"[^a-z0-9 ]+")

NON_ANSWER_MESSAGE = (
    "That doesn't give the system anything to diagnose. Write your best guess, even if unsure, "
    "and a sentence on why: misconceptions show up in reasoning, not in 'I don't know'."
)
NEEDS_REASONING_MESSAGE = (
    "This is your own question, so there is no answer key. Explain your reasoning in at least "
    f"{MIN_REASONING_WORDS} words so the model has something to diagnose."
)


def _norm(text: str) -> str:
    return " ".join(NON_WORD.sub(" ", text.lower().replace("'", "")).split())


def has_answer_key(question: Question) -> bool:
    return bool(question.correct_answer.strip())


def screen_response(question: Question, response: LearnerResponse) -> str | None:
    answer = _norm(response.answer)
    working = _norm(response.working)
    if answer in NON_ANSWERS and (working in NON_ANSWERS or len(working.split()) < MIN_REASONING_WORDS):
        return NON_ANSWER_MESSAGE
    if not has_answer_key(question) and len(working.split()) < MIN_REASONING_WORDS:
        return NEEDS_REASONING_MESSAGE
    return None
