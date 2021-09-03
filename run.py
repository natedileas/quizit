import logging

import quizit.index

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    quizit.index.socketio.run(quizit.index.app, debug=True, host="0.0.0.0")

    # TODO db / save players or
