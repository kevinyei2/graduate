# Instagram 設定教學

需要：Instagram **創作者或商業帳號**（你已經是創作者帳號 ✔）。
不需要 Facebook 粉絲專頁，但需要一個 Facebook 帳號來登入 Meta 開發者後台。約 15 分鐘。

## 步驟 1：註冊 Meta 開發者
1. 打開 https://developers.facebook.com/ → 右上「開始使用」，用 Facebook 帳號登入。
2. 依指示驗證手機或信箱，身分選「開發者」。

## 步驟 2：建立 App
1. 「我的應用程式」→「建立應用程式」。
2. 名稱：`social-uploader`，聯絡信箱填你的。
3. 使用案例（Use case）選「**管理 Instagram 上的訊息和內容**」（Manage messaging & content on Instagram）。
4. 商家資產組合：選「我還不想連結商家資產組合」→ 一路「下一步」→「建立應用程式」。

## 步驟 3：設定 Instagram API
1. 在 App 主控台左側 →「使用案例」→ 剛剛的 Instagram 使用案例 →「自訂 / 設定」。
2. 進到「**使用 Instagram 登入設定 API**」（API setup with Instagram login）。
3. 權限確認有 `instagram_business_basic` 和 `instagram_business_content_publish`。

## 步驟 4：產生存取權杖
1. 同一頁的「產生存取權杖」（Generate access tokens）→「新增帳號」。
2. 用你的 **Instagram 創作者帳號**登入並允許。
   - 如果顯示權限不足：到左側「應用程式角色」→「角色」→ 新增「Instagram 測試人員」填你的 IG 帳號，
     再到 IG App → 設定 → 「網站權限 / 應用程式和網站」→「測試人員邀請」按接受，然後重來一次。
3. 帳號旁按「**產生權杖**」→ 複製那一長串（通常以 `IGAA` 開頭）。
   這個權杖等同你的 IG 發文權限，**不要貼到聊天室或傳給別人**。

## 步驟 5：在本工具連結
1. 「設定」→ Instagram → 貼上權杖 →「驗證並儲存」。
2. 看到「✔ 已連結：@你的帳號」就完成了。
3. 權杖有效 60 天，工具開著時會在到期前自動續期。如果很久沒開導致過期，重新產生一次貼上即可。

## 關於 App 審核
只發到**你自己的帳號**的話，App 維持「開發模式」就能用，**不需要送審**。
