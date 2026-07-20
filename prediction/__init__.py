"""prediction — config-driven revenue-surprise nowcasting package.

Importing this package runs every @register_* decorator (through the star-imports below), so all
channels / targets / arms / prompts / baselines / llms populate the Registry on `import prediction`.
"""
from prediction.channels import *  # noqa: F401,F403
from prediction.targets import *  # noqa: F401,F403
from prediction.arms import *  # noqa: F401,F403
from prediction.prompts import *  # noqa: F401,F403
from prediction.baselines import *  # noqa: F401,F403
from prediction.data import *  # noqa: F401,F403
from prediction.predict import *  # noqa: F401,F403
from prediction.evaluate import *  # noqa: F401,F403
from prediction.run import *  # noqa: F401,F403
