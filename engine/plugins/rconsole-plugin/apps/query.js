import { replyWithRetry } from "../utils/retry.js";
import axios from "axios";
import fetch from "node-fetch";
// 常量
import { CAT_LIMIT, COMMON_USER_AGENT } from "../constants/constant.js";
import config from "../model/config.js";
import { sendImagesInBatches } from "../utils/yunzai-util.js";

export class query extends plugin {

    constructor() {
        super({
            name: "R插件查询类",
            dsc: "R插件查询相关指令",
            event: "message.group",
            priority: 500,
            rule: [
                {
                    reg: "^#医药查询(.*)$",
                    fnc: "doctor",
                },
                {
                    reg: "^#cat$",
                    fnc: "cat",
                },
                {
                    reg: "^#推荐软件$",
                    fnc: "softwareRecommended",
                },
                {
                    reg: "^#买家秀$",
                    fnc: "buyerShow",
                },
                {
                    reg: "^#累了$",
                    fnc: "cospro",
                }
            ],
        });
        // 加载配置
        this.toolsConfig = config.getConfig("tools");
        this.imageBatchThreshold = this.toolsConfig.imageBatchThreshold || this.toolsConfig.douyinImageBatchThreshold || 50;
    }

    async doctor(e) {
        const keyword = e.msg.replace("#医药查询", "").trim();
        const url = `https://server.dayi.org.cn/api/search?keyword=${encodeURIComponent(keyword)}&pageNo=1&pageSize=10`;
        console.log(`[R插件][医药查询] 请求URL: ${url}`);
        try {
            // Node.js需要禁用SSL验证（该服务器证书有问题）
            const { Agent } = await import('https');
            const response = await axios.get(url, {
                httpsAgent: new Agent({ rejectUnauthorized: true })
            });
            const res = response.data.list;

            if (!res || res.length === 0) {
                e.reply("未找到相关医药信息");
                return true;
            }

            let msg = res.map(element => {
                const title = this.removeTag(element.title);
                const intro = this.removeTag(element.introduction);
                const template = `📌 ${title} - ${element.secondTitle}\n\n📝 简介：${intro}`;
                return {
                    message: { type: "text", text: template },
                    nickname: e.sender.card || e.user_id,
                    user_id: e.user_id,
                };
            });

            await replyWithRetry(e, Bot, await Bot.makeForwardMsg(msg));
        } catch (err) {
            console.error(`[R插件][医药查询] 请求失败:`, err.message);
            e.reply("医药查询失败，请稍后重试");
        }
        return true;
    }

    async cat(e) {
        const [shibes, cats] = await Promise.allSettled([
            fetch(`https://shibe.online/api/cats?count=${CAT_LIMIT}`).then(data => data.json()),
            fetch(`https://api.thecatapi.com/v1/images/search?limit=${CAT_LIMIT}`).then(data =>
                data.json(),
            ),
        ]);

        const shibeUrls = shibes.status === "fulfilled" ? shibes.value : [];
        const catUrls = cats.status === "fulfilled" ? cats.value.map(item => item.url) : [];
        const reqRes = [...shibeUrls, ...catUrls];

        e.reply("涩图也不看了,就看猫是吧");

        const images = reqRes.map(item => ({
            message: segment.image(item),
            nickname: this.e.sender.card || this.e.user_id,
            user_id: this.e.user_id,
        }));
        await sendImagesInBatches(e, images, this.imageBatchThreshold);
        return true;
    }

    async softwareRecommended(e) {
        // 接口
        const urls = [
            "https://www.ghxi.com/ghapi?type=query&n=pc",
            "https://www.ghxi.com/ghapi?type=query&n=and",
        ];
        // 一起请求
        const promises = urls.map(url =>
            fetch(url)
                .then(resp => resp.json())
                .catch(err => logger.error(err)),
        );
        const results = await Promise.allSettled(promises);
        const msg = results
            .filter(result => result.status === "fulfilled") // 只保留已解决的 Promise
            .flatMap(result =>
                result.value.data.list.map(element => {
                    const template = `推荐软件：${element.title}\n地址：${element.url}\n`;
                    return {
                        message: { type: "text", text: template },
                        nickname: e.sender.card || e.user_id,
                        user_id: e.user_id,
                    };
                }),
            );

        // 异步操作
        e.reply(await Bot.makeForwardMsg(msg));

        return true;
    }

    async buyerShow(e) {
        try {
            // 使用素言网API获取买家秀
            const resp = await fetch("https://api.suyanw.cn/api/tbmjx.php?return=json");
            const data = await resp.json();

            if (data.imgurl) {
                e.reply(segment.image(data.imgurl));
            } else {
                e.reply("获取买家秀失败");
            }
        } catch (error) {
            console.error(`[R插件][买家秀] API失败: ${error.message}`);
            e.reply("获取买家秀失败，请稍后重试");
        }
        return true;
    }

    async cospro(e) {
        // 恢复原来的cos图API
        let [res1, res2] = (
            await Promise.allSettled([
                fetch("https://imgapi.cn/cos2.php?return=jsonpro").then(resp => resp.json()),
                fetch("https://imgapi.cn/cos.php?return=jsonpro").then(resp => resp.json()),
            ])
        )
            .filter(result => result.status === "fulfilled")
            .map(result => result.value);
        let req = [...res1.imgurls, ...res2.imgurls];
        e.reply("哪天克火掉一定是在这个群里面...");
        let images = req.map(item => ({
            message: segment.image(encodeURI(item)),
            nickname: this.e.sender.card || this.e.user_id,
            user_id: this.e.user_id,
        }));
        await sendImagesInBatches(e, images, this.imageBatchThreshold);
        return true;
    }


    // 删除标签
    removeTag(title) {
        const titleRex = /<[^>]+>/g;
        return title.replace(titleRex, "");
    }
}
