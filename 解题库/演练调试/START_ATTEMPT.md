# 命令行启动尝试：尚未启动演练

2026-09-13，本轮目标为启动问题4演练，不调用正式测试。

已从当前 EXE 的内嵌前端确定 `StartPractice(problemNo, visibleEventCount)`，绑定编号31672008；后端存在 `appui.Service.StartPractice` 和 `runcontroller.Controller.StartPractice`。显示条数默认1000。此绑定依赖 Wails 内部运行时，不是2026端口的机器人接口。

在确认没有活动 `behavior.journal.jsonl` 后，原空闲进程已关闭。尝试用仅对子进程生效的 WebView2 环境变量启用回环调试端口9226；未修改注册表、持久环境变量、EXE或正式测试接口。重新运行的进程30540仍在，机器人端口2026监听，但9226没有开放，也没有生成活动演练日志。

第一次启动的自有后台进程40292因没有主窗口句柄无法正常关闭，在再次确认没有活动测试后定向终止；随后尝试显式子进程环境参数，仍无调试端口。没有继续反复重启。

定位到 EXE 中的 `webviewloader.preventEnvAndRegistryOverrides` 符号。Wails对应加载器源码会清空 `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` 和脚本调试设置，连注册表覆盖也排除；这与实测子进程不含调试参数一致。来源：
https://github.com/wailsapp/wails/blob/master/v3/internal/webview2/webviewloader/env_create.go

仅找到内部入口不等于已建立外部调用通道。没有尝试二进制补丁、进程注入、修改构建身份或替换服务器。本轮没有调用 `/enter`、`StartPractice` 或任何正式启动函数，不得记作演练启动成功。

当前约束仍是“不得操作桌面”。继续通过界面启动需要用户解除这一项限制；后续机器人动作仍可用已有命令行演练运行器。未生效的临时重启脚本已移除，以免误用；诊断记录保留于本文件。独立虚拟环境安装了 websocket-client 1.9.2，但尚未进行任何调试通道调用。
