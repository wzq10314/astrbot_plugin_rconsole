# 来源说明

本项目的媒体功能根据用户提供的 `rconsole-plugin-master.zip` 核对并重实现。上游地址：https://gitee.com/kyrzy0416/rconsole-plugin 。

- 抖音流程依据：`apps/tools.js` 的 douyin / tryDouyinSsrBackup，`utils/douyin.js`，`config/tools.yaml`，`guoba.support.js`。
- 小红书流程依据：`apps/tools.js` 的 xhs，`constants/constant.js` 的 XHS_NO_WATERMARK_HEADER。
- `vendor/a-bogus.cjs` 原样复制自上游 `utils/a-bogus.cjs`，SHA-256 为 `7bbb81a84bf8976223085974411ec51e896a4081dc9d20d8fbff6c68e3c11dd7`；保留该文件全部注释、署名及使用说明。其文件头另有“仅学习交流、禁止商业和非法使用”声明；不将这个第三方文件重新授权为无此限制的代码。
- 保留上游仓库提供的 MulanPSL-2.0 `LICENSE`。本版新增的 Python 实现与调用包装采用 MulanPSL-2.0；第三方签名文件的原声明见文件自身。

未复制上游的账号 Cookie、外部解析服务凭据或私有配置。发行包所有 Cookie 字段为空。文件读取或网页解析不执行来自平台页面的 JavaScript。
