import tiktoken


def num_tokens_from_string(string: str, encoding_name: str) -> int:
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


print(num_tokens_from_string("привет, я егор", "cl100k_base"))
