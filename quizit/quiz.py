"""
Quiz specific code
"""

import glob
import pathlib
import yaml

QUIZ_DIR = pathlib.Path(__file__).parent.resolve() / 'quizzes'


def available_quizzes():
    output = []
    for quiz in glob.glob(QUIZ_DIR / "*.yaml"):
        file = open(quiz, "r")
        data = yaml.load(file, Loader=yaml.FullLoader)
        output.append({"data": data, "file": quiz})

    return output


class Quiz:
    def __init__(self, quiz_path):
        try:
            file = open(quiz_path, "r")
        except FileNotFoundError:
            print("File not found!")
            return

        self.file = quiz_path
        self.data = yaml.load(file, Loader=yaml.FullLoader)
        self._current = -1
        self.answers = []

    def next_question(self):
        n_questions = len(self.data["questions"]) - 1

        if self._current < n_questions:
            self._current += 1
        else:
            self._current = -2
            return {'type': 'end'}

        question = self.data["questions"][self._current]

        if question.get('format', False):
            # TODO add docs about what is available here.
            question['prompt'] = question['prompt'].format(
                n_questions=n_questions,
                n_answers=len(self.answers),
                current_question=self._current,
            )

        return question

    def got_answer(self, answer_json):
        # TODO store this info so it can be injected into the template.
        self.answers.append(answer_json)
