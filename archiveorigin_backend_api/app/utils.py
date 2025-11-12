import random
import string

def random_shortcode(length: int = 6) -> str:
    alphabet = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return ''.join(random.choice(alphabet) for _ in range(length))
