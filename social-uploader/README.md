# 多平台上傳工具（YouTube / Instagram / TikTok）

在自己電腦上開一個網頁，選一次影片、分別填各平台的說明和 hashtag，
就能**立即**或**排程**同時發佈到 YouTube、Instagram Reels、TikTok。
全部走各平台**官方 API**。

## 功能

- 拖一支影片 → 勾選要發的平台 → 送出
- 共用說明 / hashtag，各平台也可以分別改
- 立即發佈或排程（每個平台可以設不同時間）
- 佇列頁看每個平台的狀態、成功網址、錯誤訊息，失敗可以一鍵重試
- Instagram 權杖到期前自動續期
- TikTok 已做好，但預設**關閉**（等開發者 App 審核過再打開）

## 安裝與啟動

需要 Python 3.10 以上（https://www.python.org/downloads/ ，Windows 安裝時記得勾「Add Python to PATH」）。

- **Windows**：雙擊 `start.bat`
- **macOS / Linux**：在終端機執行 `./start.sh`

第一次會自動安裝需要的套件，接著瀏覽器會打開 http://127.0.0.1:5000 。

> **排程注意**：排程只在這個程式開著的時候才會執行。到時間電腦是關的話，
> 下次開啟時會自動補發。

## 第一次設定（照順序做）

1. [YouTube 設定](docs/setup-youtube.md)
2. [Instagram 設定](docs/setup-instagram.md)
3. [TikTok 設定](docs/setup-tiktok.md)（可之後再做）

## 資料存放位置

所有憑證、權杖、影片暫存、資料庫都在 `data/` 資料夾，已被 `.gitignore` 排除，
**不會**上傳到 GitHub。不要把這個資料夾傳給別人。

## 各平台限制

| 平台 | 限制 |
|---|---|
| YouTube | 每日 API 額度預設約可上傳 6 支；Google 稽核通過前，上傳的影片會被強制設為「私人」 |
| Instagram | 需創作者或商業帳號；Reels 長度 3 秒～15 分鐘；每 24 小時有發文上限 |
| TikTok | App 審核前直接發佈只能「僅自己可見」，或用「草稿匣模式」讓你在手機上按發佈 |
