# 简账 个人记账与预算分析系统

运行环境：Python 3.10 或更高版本，无第三方依赖，无需联网。

1. 解压整个项目，保持 static 文件夹与 app.py 同级。
2. Windows 双击 start.bat，或在此目录运行 `python app.py`。
3. 浏览器打开 http://127.0.0.1:8000 。保持终端运行。
4. 端口冲突时执行 `python app.py --port 8001` 并打开对应端口。

首次启动数据库为空。可手动录入收入、支出，设置月度预算，按月查看并导出 CSV。
数据库自动保存到 accounts.db。关闭程序后复制该文件可作备份。

## 文件说明
app.py：HTTP 接口、数据校验、统计、SQLite 存储。
static/index.html、style.css、app.js：界面、样式、交互。
test_app.py：自动测试。运行 `python -m unittest -v test_app`。
示例数据.csv：课堂演示输入参考，并非真实个人数据；应用未实现 CSV 导入。

## 范围
单用户本机应用，绑定 127.0.0.1，无登录、多用户、外网部署或云端AI服务。
预算提醒使用固定规则。AI 用于开发辅助，不会在运行时上传账目。
删除需确认。金额保存为整数分，导出支持中文 UTF-8 BOM。
备注通过 textContent 显示，数据库使用参数化 SQL。
对外分享源码前请勿包含个人 accounts.db。
