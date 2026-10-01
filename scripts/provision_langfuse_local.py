"""Generate local-only bootstrap secrets once. Never print credentials."""

import json
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / "ops/secrets"
    target.mkdir(parents=True, exist_ok=True)
    env_path = target / "langfuse.env"
    if env_path.exists():
        print("Langfuse local bootstrap already exists; not overwritten")
        return
    values = {
        key: secrets.token_hex(24)
        for key in (
            "LF_POSTGRES_PASSWORD",
            "LF_CLICKHOUSE_PASSWORD",
            "LF_REDIS_PASSWORD",
            "LF_MINIO_PASSWORD",
            "NEXTAUTH_SECRET",
            "SALT",
            "LANGFUSE_INIT_USER_PASSWORD",
        )
    }
    values.update(
        {
            "ENCRYPTION_KEY": secrets.token_hex(32),
            "LANGFUSE_INIT_ORG_ID": "veridra-local",
            "LANGFUSE_INIT_ORG_NAME": "Veridra Local",
            "LANGFUSE_INIT_PROJECT_ID": "veridra-operations",
            "LANGFUSE_INIT_PROJECT_NAME": "Veridra metadata-only",
            "LANGFUSE_INIT_PROJECT_PUBLIC_KEY": "pk-lf-" + secrets.token_hex(20),
            "LANGFUSE_INIT_PROJECT_SECRET_KEY": "sk-lf-" + secrets.token_hex(32),
            "LANGFUSE_INIT_USER_EMAIL": "owner@veridra.local",
            "LANGFUSE_INIT_USER_NAME": "Veridra Local Owner",
        }
    )
    env_path.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
    )
    (target / "langfuse-export.json").write_text(
        json.dumps(
            {
                "public_key": values["LANGFUSE_INIT_PROJECT_PUBLIC_KEY"],
                "secret_key": values["LANGFUSE_INIT_PROJECT_SECRET_KEY"],
            }
        )
    )
    (target / "langfuse-owner-login.txt").write_text(
        "Local URL: http://localhost:3035\nEmail: "
        + values["LANGFUSE_INIT_USER_EMAIL"]
        + "\nPassword: "
        + values["LANGFUSE_INIT_USER_PASSWORD"]
        + "\n"
    )
    print(
        "Generated ignored local Langfuse bootstrap and owner login file; no secrets printed"
    )


if __name__ == "__main__":
    main()
