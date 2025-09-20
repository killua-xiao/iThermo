// 调度函数：按日触发，向 Netlify Build Hook 发送 POST 以触发新构建，从而刷新 data.json
// 注意：请在 Netlify 环境变量中配置 NETLIFY_BUILD_HOOK_URL

export const config = {
  schedule: "0 0 * * *", // 00:00 UTC
};

export default async (request, context) => {
  const hook = process.env.NETLIFY_BUILD_HOOK_URL;
  if(!hook){
    return new Response(JSON.stringify({ ok:false, error:'NETLIFY_BUILD_HOOK_URL not set' }), {status:500});
  }
  try{
    const res = await fetch(hook, { method:'POST' });
    const text = await res.text();
    return new Response(JSON.stringify({ ok:true, status:res.status, body:text.slice(0,200) }), {status:200});
  }catch(err){
    return new Response(JSON.stringify({ ok:false, error:String(err) }), {status:500});
  }
};