import os.path

import environ


env = environ.Env(
    DEBUG=(bool, False)
)

if os.path.exists('.env'):
    environ.Env.read_env('.env')

__all__ = [
    'env',
]
