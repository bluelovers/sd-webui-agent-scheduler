# Change Log

All notable changes to this project will be documented in this file.
See [Conventional Commits](https://conventionalcommits.org) for commit guidelines.

# [0.0.0](https://github.com/bluelovers/sd-webui-agent-scheduler/compare/ui@0.0.0...ui@0.0.0) (2026-11-20)

**Note:** Version bump only for package ui





# 0.0.0 (2026-11-20)


### BREAKING CHANGES

* **ui:** 重構 UI 模組化架構並拆分功能組件
* **ui:** 重構佇列切換邏輯並模組化 DOM 查詢與事件處理
* update layout



### 🐛　Bug Fixes

* [#124](https://github.com/bluelovers/sd-webui-agent-scheduler/issues/124) enqueue button sometime not working ([097fe4e](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/097fe4e5c97612520b3e4d80d44f36088c53e2c4))
* buttons on history tab have no color ([3cf75f5](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/3cf75f5e1b483743e42d68fe16b9f0e3a80334a4))
* duplicate task_id ([07476d8](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/07476d89c7e9239929f82471b2596d1a2a820812))
* typos ([e9056ee](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/e9056ee69c7d5cc2da1d8ea5924241fa09782974))
* broken layout in Vlad fork ([a53ccc4](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/a53ccc494d2ec118a1ea5d5a4364433c294d4ded))
* keyboard shortcut setting not visible in vlad fork ([9bf2aec](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/9bf2aeca3c00b78c6901849a91772112e36ea358))
* **scheduler:** 修正模型卸載按鈕的元件型別判斷與佈局樣式 ([27877f7](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/27877f7d89a59d3be3b2cf2284fa83acfef71f84))


### ✨　Features

* import/export ([b6965ad](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/b6965ad05d25b383468ea0289bd6d0e0a92aad82))
* always queue task with checkpoint value on UI ([9e5a0ba](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/9e5a0ba800d194a96db8592481271d525017edab))
* queue with name & queue with all checkpoints ([facdfd0](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/facdfd0f83ba5062e81473149ca3c072a2da9c03))
* clear queue & history ([cc75abc](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/cc75abcc9b990711a8ca45a7687be84fe8961ec4))
* update task ([dff02bd](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/dff02bd0d2e16cc64fbd94770e58c4809530124d))
* enqueue keyboard shortcut ([26b0260](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/26b0260db655a71742fc997d733c008af469ab5f))
* **agent_scheduler:** 優化 checkpoint 覆寫邏輯並提升 UI 相容性 ([2a76aef](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/2a76aef3376b9bcf0d1e9f6bf161a5f5c7962d60))
* **ui:** 新增提示詞複製功能與相關樣式 ([ccf105c](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/ccf105c274bf4ac8b19ec7366d9970e4f1badd7b))
* **ui:** 實作歷史紀錄未讀狀態標示與書籤欄位優化 ([5400cdd](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/5400cddb7925a1385496c2db006750a12bca3a47))
* **ui:** 為執行中任務新增視覺強調樣式 ([920d2c8](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/920d2c88b1fdb098e39e48353520f873a031a960))
* **ui:** 整合任務類型與參數資訊至單一欄位 ([7b802ea](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/7b802ea4467b1d10ab1031d31c07c17722572ef5))
* **ui:** 優化佇列狀態顯示元件並強化前端顯示邏輯 ([ec9f7eb](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/ec9f7ebdea2bba91f00f555ac27375814c884659))
* **ui:** 新增 Enqueue 快速控制列與輸出目錄跳過選項 ([b2098d2](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/b2098d2b794a2da16578fe9fdc26a2073167ca71))


### 📦　Code Refactoring

* **ui:** 固定分頁大小並停用自動分頁 ([94f2584](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/94f2584a5800be92eeab8516546cba0ca3710a70))
* **ui:** 實作欄位狀態持久化並抽象化表格邏輯 ([a972175](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/a97217580afc5b5241042b5f95925405459d261f))
* **ui:** 重構 UI 模組化架構並拆分功能組件 ([08ad4f6](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/08ad4f699bfab51bfa5bd64572fc3d73c0ad1edb))
* **ui:** 重構佇列切換邏輯並模組化 DOM 查詢與事件處理 ([fa5c433](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/fa5c4331731a5905caac78ee2b8527bf9d38655b))
* **ui:** 重構佇列切換邏輯並實作狀態訂閱機制 ([669af3d](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/669af3dbe4db231d2d6b8919573d1993b4f7e08c))


### 💎　Styles

* update layout ([29cf4c0](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/29cf4c03fd221deb1cc38ba0409b489a8f935dc1))
* disable box-shadow ([90626d4](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/90626d43a063e8ab8d5f483f8c6b3d804f137edf))
* update button style ([2df5e50](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/2df5e50572e74c2398e66fc041fae98cf1b52f8b))
* **ui:** 優化表格欄位配置與列高設定 ([2ed3512](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/2ed351207c5e273577d5ce3bac95516db5b9bac4))
* **ui:** 優化狀態標籤樣式與初始化視覺效果 ([0ec3748](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/0ec3748e9e651bb8904c81ae2b0aaa8a4e9edf3d))
* **ui:** 優化狀態切換動畫與重構按鈕綁定邏輯 ([d83a634](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/d83a634600fa672608dd08dca30cd4c44af3920b))


### 🛠　Build System

* update build ([18b05b0](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/18b05b0a4f79fcae6d10236c05b965a2b29a3160))
* avoid miss deps ([bd68986](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/bd689863d9fee3a63ccb84ae18eeea4b72c07c68))


### ♻️　Chores

* show time in local timezone ([ab9491c](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/ab9491c2d585e1eac6c5c82d967588c29b5d58cf))
* better script_args serialization ([1eefb2f](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/1eefb2fab7a27204042281e874d48a2480fa7786))
* use iife format for js ([8198489](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/8198489fd42883d3af119e219c320ba4853802c8))
* basic support for stable-diffusion-webui-ux ([9180642](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/9180642eb103706912fbfe7d46eb1e0fde1cfc78))
* improve disable shortcut ui ([c291dc5](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/c291dc56435e0b8634313d0ae57cd276c9040187))
* add setting to disable keyboard shortcut ([fbf7b92](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/fbf7b929e225f3c944e7680400bf41b14131475f))
* update notyf style & message ([d785c01](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/d785c01787468746ac4fd8301b3a6fcbf33074f0))
* UI updates and bug fixing ([4717477](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/471747767f2b004ae0d866a2df5942e99d49061b))
* feature updates ([4f73394](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/4f7339468c742999b04c526ce7df395015d03b40))


### 🔖　Miscellaneous

* Fix Enqueue button not appearing in compact prompt layout ([20bed84](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/20bed846bbdc2cc087f12c486322f0a30adea777))
* Update dependencies ([73f549c](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/73f549ca7c3d2ce59a6dc63ec335e9c7e8a837cc))
* Update dependencies ([2692316](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/2692316feea47dbdd76d5ffe47d49414922d0cb5))
* Fix styling issue with task status ([28cc786](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/28cc7862b3bd50bf3847ad6aa07017a11177e900))
* Small fix ([be167e3](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/be167e33761c173254e8fadc6bd321ded1d9c1ca))
* Update dependencies ([33213ef](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/33213ef513663236a2dd5268ec5bb68595ea7813))
* Add support for sd-webui v1.7.0 ([05eca59](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/05eca59c475a7971e47f13a599dfe9129fb41ad2))
* fix window.submit is not available in SD.Next ([8970f48](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/8970f485b767929cb36b5fee0df1d98840023f2a))
* improve setting layout ([02da7ab](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/02da7abf4be093499c32c0f758621838968b2212))
* add page_size & auto requeue failed tasks settings ([c32395e](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/c32395e42a6095db79ad6715e28d578984a6c89f))
* implement api to get samplers & models to be able to run without --api ([99b2caf](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/99b2cafbc2b4a2fc93ffcabd56b0ff915396d1f1))
* add save & save zip buttons ([669ebcc](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/669ebcc7fc3280e953af5bb6566f42239204479f))
* fix css layout ([310bb4e](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/310bb4eace9e7fc03074dd49a91797bd6df2c43b))
* Fix CSS `.block` selector conflict ([af1293e](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/af1293e18ba9fc934d9b75cc89ec21257496f449))
* Revert changes and delay progress requests only ([7e6b461](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/7e6b461db44b6c16f816f810a5756285b99d1a05))
* Small fix ([41799de](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/41799deba8d4fedaf33efebda6e4e0dc3e6cb7dd))
* Fix progress bar not showing on page load ([2b75548](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/2b75548c286214c5a534315c48b556847e914c2f))
* Fix highlight line position ([efb0eac](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/efb0eac31cb72afcee8043761e9278232812d3db))
* Fix pending tasks refresh button not working ([e9c6974](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/e9c6974677a84f2cfde6534d5b902d430fda74ba))
* Improve date formatting and fix CSS rules ([5a54f78](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/5a54f7861a612ea737104b0074eb2c5d0687a75f))
* Fixed issue with tasks not sorting ([f521d58](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/f521d5847f58aff95919d0d899843d70c9e6733e))
* Small fixes ([84abd84](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/84abd84ca42050bfae1c60206a4adcdb570c6d47))
* Use accent color for running task text color ([c638092](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/c638092fc9530fdc6c878b5b5fa01f8d2c41de21))
* Small fixes ([a37c71f](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/a37c71f535faa9aaa0e6adca3f9e6d36a7b3a5a4))
* Add highlight + make it more Gradio theme friendly ([eb758d6](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/eb758d65c062fcee7c623c8bc13db7027d765f39))
* Fix layout and support for next version ([745df4c](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/745df4cbe243e35b1338ac4acf093ef539e58f72))
* Fix blinking cell borders for running tasks ([25b8844](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/25b8844facc04457fd2b74cfaf7e9dea8223ecbe))
* Make the theme dynamically sync to Gradio ([487e4ff](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/487e4ff32c591cef2cffdb403a5e9e3be671c1e5))
* feature update ([828f1d9](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/828f1d93d1566bcfd367d5f62588036d283f2431))
* bugs fixing ([79a5357](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/79a53571887971c97f967f4e489805d45fbc668e))
* feature update ([ce2b9b4](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/ce2b9b4eb9d8aeb1b2187176a5cf13b4d89f195f))
* refactor code ([48ad5b6](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/48ad5b6d22718a72ebb7e1918153d066e9225da4))
* feature update ([57f2351](https://github.com/bluelovers/sd-webui-agent-scheduler/commit/57f23512cff5d29ca1bff498d5262e1d53e5e951))
