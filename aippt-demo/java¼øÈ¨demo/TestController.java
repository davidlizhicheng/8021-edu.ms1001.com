package com.skyTest.pdf.ppt;

import cn.hutool.http.HttpRequest;
import cn.hutool.http.HttpResponse;
import cn.hutool.http.HttpUtil;

/**
 * @author ADMIN
 */
public class TestController {
    public static void main(String[] args) {
        long timestamp = System.currentTimeMillis() / 1000;
        System.out.println("timestamp = " + timestamp);
        String signature = SignUtil.getSignature(timestamp);
        System.out.println("signature = " + signature);

        // uid为自定义，用于企业方做数据隔离。建议传递企业方自己用户的唯一标识。
        // channel为渠道标识，建议传递应用名称或应用包名。
        HttpResponse execute = HttpRequest.get("https://co.aippt.cn/api/grant/token?uid=1&channel=")
                .header("x-api-key", SignUtil.API_KEY)
                .header("x-timestamp", "" + timestamp)
                .header("x-signature", signature).execute();
        System.out.println("execute.body() = " + execute.body());

    }
}
