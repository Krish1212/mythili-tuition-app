import random, string

class UtilityService:
    def __init__(self):
        pass

    def randomize_string(self, string_count):
        random_string_chars = string.ascii_letters + string.digits
        return ''.join(random.choice(random_string_chars) for _ in range(string_count))