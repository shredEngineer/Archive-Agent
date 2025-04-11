#!/bin/bash

#
# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.
#

poetry run pytest

poetry run pyright

poetry run pycodestyle archive_agent tests
