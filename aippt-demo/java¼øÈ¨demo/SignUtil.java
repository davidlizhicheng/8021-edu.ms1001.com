package com.skyTest.pdf.ppt;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

/**
 * @author ADMIN
 */
public class SignUtil {
    public static final String HMAC_SHA1_ALGORITHM = "HmacSHA1";
    //API_KEY
    public static final String API_KEY = "6812123ab123a";
    //SECRET_KEY用于生成签名
    public static final String SECRET_KEY = "Wf1cpbIIR4FfSjwnrtyGEidFcGIciHlk";
    //生成签名的算法是HMAC-SHA1，使用Base64编码
    private static String genHmac(String data, String key) throws Exception {
        SecretKeySpec signingKey = new SecretKeySpec(key.getBytes(StandardCharsets.UTF_8), HMAC_SHA1_ALGORITHM);
        Mac mac = Mac.getInstance(HMAC_SHA1_ALGORITHM);
        mac.init(signingKey);
        byte[] rawHmac = mac.doFinal(data.getBytes(StandardCharsets.UTF_8));
        return Base64.getEncoder().encodeToString(rawHmac);
    }
    // 获取签名
    public static String getSignature(long timestamp){
      String data = "GET@/api/grant/token/@"+ timestamp;
      String signature = null;
      try {
          signature = genHmac(data, SECRET_KEY);
      } catch (Exception e) {
          throw new RuntimeException(e);
      }
      System.out.println("HMAC-SHA1 (Base64): " + signature);
      return signature;
    }


}
