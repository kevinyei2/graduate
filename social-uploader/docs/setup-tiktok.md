# TikTok 設定教學（可之後再做）

工具裡 TikTok 預設是**關閉**的。有兩種用法：

| 模式 | 需要審核？ | 結果 |
|---|---|---|
| 草稿匣 (inbox) | 不用，沙盒就能測 | 影片送到 TikTok App 的通知 / 草稿，你在手機上補說明後按發佈 |
| 直接發佈 (direct) | 需要通過 Content Posting API 審核 | 未審核前只能「僅自己可見」 |

## 步驟 1：註冊 TikTok 開發者
1. https://developers.tiktok.com/ → 右上「Log in」，用你的 TikTok 帳號登入。

## 步驟 2：建立 App
1. 右上頭像 →「Manage apps」→「Connect an app」→ 類型選個人 (Individual)。
2. 填 App 名稱、圖示、類別、說明。送審時還會需要「隱私權政策」和「服務條款」網址
   （可以用 GitHub Pages 放簡單的頁面，之後我可以幫你做）。
3. 平台（Platforms）勾 **Web**。

## 步驟 3：加入產品與權限
1. 「Add products」→ 加入 **Login Kit** 和 **Content Posting API**。
2. Content Posting API 裡，如要直接發佈就打開「Direct Post」。
3. Scopes 確認有 `user.info.basic`、`video.upload`、`video.publish`。
4. Login Kit 的 Redirect URI 填工具設定頁上顯示的網址：
   `http://127.0.0.1:5000/auth/tiktok/callback`
   - 如果 TikTok 不接受 http 或 127.0.0.1，告訴我，我會改成用 https 的轉接方式。

## 步驟 4：沙盒測試
1. App 頁上方切到「Sandbox」→ 建立沙盒 →「Target users」加入你自己的 TikTok 帳號。
2. 複製沙盒的 **Client Key** 和 **Client Secret**。

## 步驟 5：在本工具連結
1. 「設定」→ 平台開關勾 TikTok →「儲存」。
2. TikTok 區塊填 Client Key / Client Secret →「儲存」→「連結 TikTok 帳號」。

## 步驟 6：送審（要公開直接發佈才需要）
在 App 頁「Submit for review」，需要附上操作示範影片（錄這個工具上傳 TikTok 的過程）。
