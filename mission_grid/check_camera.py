#!/usr/bin/env python3
"""检查 OrangePi 摄像头状态"""
import paramiko

SSH_HOST = "10.209.49.217"
SSH_USER = "orangepi"
SSH_PASS = "orangepi"

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"连接 {SSH_HOST}...")
        client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=30)
        print("✓ 连接成功\n")
        
        ros_env = """
        source /opt/ros/noetic/setup.bash --extend
        source /home/orangepi/tools_ws/devel/setup.bash --extend 2>/dev/null || true
        source /home/orangepi/livox_ws/devel/setup.bash --extend 2>/dev/null || true
        source /home/orangepi/ctrl_ws/devel/setup.bash --extend 2>/dev/null || true
        export LD_PRELOAD=/home/orangepi/.local/lib/python3.8/site-packages/torch/lib/libgomp-d22c30c5.so.1
        """
        
        # 检查 ROS Master
        print("=" * 50)
        print("1. 检查 ROS Master")
        print("=" * 50)
        stdin, stdout, stderr = client.exec_command(f"{ros_env} rostopic list 2>&1 | head -5", timeout=10)
        output = stdout.read().decode('utf-8', errors='ignore')
        if "ERROR" in output or "not found" in output:
            print("✗ ROS Master 未运行")
            print("  请先运行: bash self_start.sh")
        else:
            print("✓ ROS Master 运行中")
        print()
        
        # 检查摄像头话题
        print("=" * 50)
        print("2. 检查摄像头话题")
        print("=" * 50)
        stdin, stdout, stderr = client.exec_command(f"{ros_env} rostopic list 2>/dev/null | grep -i 'camera\\|image'", timeout=10)
        output = stdout.read().decode('utf-8', errors='ignore').strip()
        if output:
            print("✓ 找到摄像头话题:")
            for topic in output.split('\n'):
                print(f"  - {topic}")
        else:
            print("✗ 未找到摄像头话题")
            print("  请检查摄像头是否启动")
        print()
        
        # 检查 web_video_server
        print("=" * 50)
        print("3. 检查 web_video_server")
        print("=" * 50)
        stdin, stdout, stderr = client.exec_command("ps aux | grep web_video_server | grep -v grep", timeout=10)
        output = stdout.read().decode('utf-8', errors='ignore').strip()
        if output:
            print("✓ web_video_server 正在运行")
        else:
            print("✗ web_video_server 未运行")
            print("  启动命令: rosrun web_video_server web_video_server")
        print()
        
        # 检查 8080 端口
        print("=" * 50)
        print("4. 检查 8080 端口")
        print("=" * 50)
        stdin, stdout, stderr = client.exec_command("netstat -tuln 2>/dev/null | grep 8080 || ss -tuln | grep 8080", timeout=10)
        output = stdout.read().decode('utf-8', errors='ignore').strip()
        if output:
            print("✓ 8080 端口已监听:")
            print(f"  {output}")
        else:
            print("✗ 8080 端口未监听")
        print()
        
        # 获取 IP 地址
        print("=" * 50)
        print("5. 网络信息")
        print("=" * 50)
        stdin, stdout, stderr = client.exec_command("hostname -I", timeout=10)
        ip = stdout.read().decode('utf-8', errors='ignore').strip()
        print(f"OrangePi IP: {ip}")
        print()
        
        # 总结
        print("=" * 50)
        print("总结")
        print("=" * 50)
        print()
        
        if not output or "ERROR" in output:
            print("请按以下步骤操作:")
            print()
            print("1. 在 OrangePi 上运行原厂脚本:")
            print("   bash self_start.sh")
            print()
            print("2. 等待启动完成后，启动 web_video_server:")
            print("   rosrun web_video_server web_video_server")
            print()
            print("3. 在地面站连接视频流:")
            print(f"   http://{ip}:8080/stream?topic=/camera/color/image_raw")
        else:
            print("系统已就绪!")
            print()
            print("在地面站连接视频流:")
            print(f"   http://{ip}:8080/stream?topic=/camera/color/image_raw")
        
    except Exception as e:
        print(f"✗ 错误: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
