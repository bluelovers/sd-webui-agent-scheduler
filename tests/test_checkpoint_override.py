"""
test_checkpoint_override.py — checkpoint 覆寫與標籤雙寫的固定測試

涵蓋:
1. apply_model_texts()（compat_a1111_forge.infotext_labels）：三態語意
   （None 原樣保留 / "System" 只清除 / 具名雙寫）、新舊標籤清理、輸入不被修改。
   apply_model_texts() (compat_a1111_forge.infotext_labels): three states,
   label cleanup, and input immutability.
2. resolve_checkpoint_title()：委由 get_closet_checkpoint_match，命中回 canonical
   title、未命中回 None。
3. apply_checkpoint_override()：None 不動作；"System" 只移除烘焙的 checkpoint；
   具名值經解析正規化為 title；解析失敗移除烘焙舊值並警告；非字典 override_settings
   正規化後寫入。

task_helpers 的模組層匯入需要 sd-webui 的 modules.*，本測試以最小替身滿足（僅供匯入、
不含任何行為）；解析結果一律由個別測試以 mock.patch 指定。

執行
    python tests/test_checkpoint_override.py
    python tests/run_tests.py
"""

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

# 讓 _support 與 agent_scheduler 可被匯入（各種呼叫方式都成立）
# Make _support and agent_scheduler importable regardless of invocation style.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _install_webui_stubs() -> None:
    """以最小替身滿足 task_helpers 的模組層匯入（僅供匯入，不含任何行為）

    回傳值替身一律由個別測試以 mock.patch 提供；stub 的
    get_closet_checkpoint_match 永遠回 None。
    """
    if "modules" in sys.modules:
        return

    modules = types.ModuleType("modules")
    for name in ("sd_samplers", "scripts", "shared", "sd_vae", "images", "txt2img", "img2img"):
        setattr(modules, name, types.ModuleType(f"modules.{name}"))
    # task_helpers 的函式註解在 def 時求值 scripts.Script（模組層）
    modules.scripts.Script = type("Script", (), {})

    sd_models = types.ModuleType("modules.sd_models")
    sd_models.get_closet_checkpoint_match = lambda search: None
    modules.sd_models = sd_models

    api_models = types.ModuleType("modules.api.models")
    api_models.StableDiffusionTxt2ImgProcessingAPI = type(
        "StableDiffusionTxt2ImgProcessingAPI", (), {}
    )
    api_models.StableDiffusionImg2ImgProcessingAPI = type(
        "StableDiffusionImg2ImgProcessingAPI", (), {}
    )
    modules_api = types.ModuleType("modules.api")
    modules_api.models = api_models
    modules.api = modules_api

    # compat paste_params 的模組層匯入需要這 5 個符號
    infotext_utils = types.ModuleType("modules.infotext_utils")
    infotext_utils.ParamBinding = type("ParamBinding", (), {})
    infotext_utils.registered_param_bindings = []
    for name in (
        "connect_paste_params_buttons",
        "create_override_settings_dict",
        "register_paste_params_button",
    ):
        setattr(infotext_utils, name, lambda *args, **kwargs: None)
    modules.infotext_utils = infotext_utils

    sys.modules["modules"] = modules
    sys.modules["modules.sd_models"] = sd_models
    sys.modules["modules.api"] = modules_api
    sys.modules["modules.api.models"] = api_models
    sys.modules["modules.infotext_utils"] = infotext_utils


_install_webui_stubs()

from agent_scheduler.compat_a1111_forge.infotext_labels import (  # noqa: E402
    MODEL_TEXT_PREFIXES,
    SYSTEM_CHECKPOINT,
    apply_model_texts,
)
from agent_scheduler import task_helpers  # noqa: E402


class FakeCheckpointInfo:
    """get_closet_checkpoint_match 的回傳值替身：只帶 title"""

    def __init__(self, title: str):
        self.title = title


class ApplyModelTextsTests(unittest.TestCase):
    """apply_model_texts：三態語意、雙標籤清理與寫入、輸入不變"""

    def test_runtime_none_keeps_texts(self):
        # Runtime Checkpoint：連既有模型標籤一併保留
        texts = ["Model hash: stale", "Seed: 42"]
        result = apply_model_texts(texts, None)
        self.assertEqual(result, texts)
        self.assertIsNot(result, texts)

    def test_system_only_removes_model_labels(self):
        texts = ["Model: stale", "Model hash: stale", "Seed: 42"]
        self.assertEqual(apply_model_texts(texts, SYSTEM_CHECKPOINT), ["Seed: 42"])

    def test_named_checkpoint_writes_both_labels(self):
        texts = ["Model hash: stale", "Model: stale", "Seed: 42"]
        result = apply_model_texts(texts, "sd/a/foo.safetensors")
        self.assertEqual(
            result,
            [
                "Seed: 42",
                "Model: sd/a/foo.safetensors",
                "Model hash: sd/a/foo.safetensors",
            ],
        )
        # 輸入不被修改 / the input list is left untouched
        self.assertEqual(texts, ["Model hash: stale", "Model: stale", "Seed: 42"])

    def test_dual_labels_cover_forge_and_legacy(self):
        # Forge Neo 以 "Model" 識別；舊環境以 "Model hash" 識別
        self.assertIn("Model: ", MODEL_TEXT_PREFIXES)
        self.assertIn("Model hash: ", MODEL_TEXT_PREFIXES)


class ResolveCheckpointTitleTests(unittest.TestCase):
    """resolve_checkpoint_title：委由 get_closet_checkpoint_match，命中回 title"""

    def test_hit_returns_canonical_title(self):
        with mock.patch.object(
            task_helpers,
            "get_closet_checkpoint_match",
            return_value=FakeCheckpointInfo("sd/a/foo.safetensors [abc123def0]"),
        ) as resolver:
            title = task_helpers.resolve_checkpoint_title("sd/a/foo.safetensors")
        self.assertEqual(title, "sd/a/foo.safetensors [abc123def0]")
        resolver.assert_called_once_with("sd/a/foo.safetensors")

    def test_miss_returns_none(self):
        with mock.patch.object(
            task_helpers, "get_closet_checkpoint_match", return_value=None
        ):
            self.assertIsNone(task_helpers.resolve_checkpoint_title("gone-model"))


class ApplyCheckpointOverrideTests(unittest.TestCase):
    """apply_checkpoint_override：三態、解析正規化與失敗退回"""

    def test_none_leaves_named_args_untouched(self):
        named_args = {"prompt": "hello"}
        task_helpers.apply_checkpoint_override(named_args, None)
        self.assertEqual(named_args, {"prompt": "hello"})

    def test_system_removes_baked_checkpoint_only(self):
        named_args = {
            "override_settings": {
                "sd_model_checkpoint": "old",
                "CLIP_stop_at_last_layers": 2,
            }
        }
        task_helpers.apply_checkpoint_override(named_args, SYSTEM_CHECKPOINT)
        self.assertEqual(
            named_args["override_settings"], {"CLIP_stop_at_last_layers": 2}
        )

    def test_named_checkpoint_is_normalized_to_title(self):
        # UI 任務存 name 形式也應被正規化為 canonical title
        named_args: dict = {}
        with mock.patch.object(
            task_helpers,
            "get_closet_checkpoint_match",
            return_value=FakeCheckpointInfo("sd/a/foo.safetensors [abc123def0]"),
        ):
            task_helpers.apply_checkpoint_override(named_args, "sd/a/foo.safetensors")
        self.assertEqual(
            named_args["override_settings"]["sd_model_checkpoint"],
            "sd/a/foo.safetensors [abc123def0]",
        )

    def test_unresolvable_removes_baked_value_and_warns(self):
        named_args = {"override_settings": {"sd_model_checkpoint": "baked-old"}}
        with mock.patch.object(
            task_helpers, "get_closet_checkpoint_match", return_value=None
        ):
            with mock.patch.object(task_helpers, "log") as fake_log:
                task_helpers.apply_checkpoint_override(named_args, "gone-model")
        self.assertNotIn("sd_model_checkpoint", named_args["override_settings"])
        fake_log.warning.assert_called_once()
        self.assertIn("gone-model", fake_log.warning.call_args[0][0])

    def test_non_dict_override_settings_is_normalized(self):
        named_args = {"override_settings": "corrupted"}
        with mock.patch.object(
            task_helpers,
            "get_closet_checkpoint_match",
            return_value=FakeCheckpointInfo("t [h]"),
        ):
            task_helpers.apply_checkpoint_override(named_args, "whatever")
        self.assertEqual(
            named_args["override_settings"], {"sd_model_checkpoint": "t [h]"}
        )


if __name__ == "__main__":
    unittest.main()
