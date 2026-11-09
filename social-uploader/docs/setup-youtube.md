# YouTube 設定教學

需要：一個能登入 YouTube 頻道的 Google 帳號。約 15 分鐘。

## 步驟 1：建立 Google Cloud 專案
1. 打開 https://console.cloud.google.com/ ，用你的 Google 帳號登入（第一次會要求同意服務條款）。
2. 左上角專案選單 →「新增專案」→ 名稱填 `social-uploader` →「建立」。
3. 確認左上角已切換到這個專案。

## 步驟 2：啟用 YouTube Data API v3
1. 上方搜尋列輸入 `YouTube Data API v3` → 點進去 →「啟用」。

## 步驟 3：設定 OAuth 同意畫面
1. 左側選單 →「API 和服務」→「OAuth 同意畫面」（新版介面叫「Google Auth Platform」）→「開始」。
2. 應用程式名稱：`social-uploader`；使用者支援電子郵件：選你的信箱。
3. 目標對象（User type）：選「**外部 (External)**」。
4. 聯絡資訊填你的信箱 → 同意政策 →「建立」。
5. 「目標對象 (Audience)」頁 →「測試使用者」→ 新增**你自己要上傳影片的那個 Google 帳號**。
6. **重要**：同一頁把「發布狀態」按「發布應用程式 (Publish app)」改成「**正式版 (In production)**」。
   - 留在「測試中」的話，授權每 **7 天**就會失效，要一直重新連結。
   - 改成正式版但沒經過 Google 驗證也沒關係（只給自己用），登入時會看到「Google 尚未驗證這個應用程式」，
     點「進階」→「前往 social-uploader（不安全）」即可。

## 步驟 4：建立 OAuth 用戶端
1. 「用戶端 (Clients)」→「建立用戶端」。
2. 應用程式類型：**電腦版應用程式 (Desktop app)**，名稱隨意 →「建立」。
3. 在跳出的視窗按「**下載 JSON**」。這個檔案是私密的，不要傳給別人、不要貼到聊天室。

## 步驟 5：在本工具連結
1. 啟動工具 → 「設定」→ YouTube → 上傳剛剛的 JSON →「上傳」。
2. 按「連結 YouTube 帳號」→ 選你的頻道帳號 → 允許權限。
3. 看到「✔ 已連結頻道：xxx」就完成了。

## 步驟 6（建議）：申請稽核，解除「強制私人」
2020 年後建立、還沒通過稽核的 API 專案，上傳的影片會被 YouTube 鎖成**私人**。
在通過稽核之前，可以先用工具上傳，再到 YouTube Studio 手動改成公開。

要解除限制：填寫 YouTube 的「API Services - Audit and Quota Extension Form」
（https://support.google.com/youtube/contact/yt_api_form ），用途寫「個人頻道自用的多平台上傳工具」。
同一份表單也可以申請提高每日上傳額度。
