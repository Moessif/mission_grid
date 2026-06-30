#!/usr/bin/env python3
"""SSH 连接 OrangePi 编译 ROS 包"""
import paramiko
import sys

SSH_HOST = "10.209.49.217"
SSH_USER = "orangepi"
SSH_PASS = "orangepi"

def ssh_exec(client, command, timeout=300):
    """执行远程命令并输出结果"""
    print(f"\n>>> 执行: {command}")
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    
    # 读取输出
    out = stdout.read().decode('utf-8', errors='ignore')
    err = stderr.read().decode('utf-8', errors='ignore')
    
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    
    return stdout.channel.recv_exit_status()

def main():
    print("=" * 60)
    print("SSH 连接 OrangePi 编译 ROS 包")
    print("=" * 60)
    
    # 创建 SSH 客户端
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # 连接
        print(f"\n[1/5] 连接 {SSH_HOST}...")
        client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=30)
        print("✓ 连接成功")
        
        # Source ROS 环境
        ros_env = """
        source /opt/ros/noetic/setup.bash --extend
        source /home/orangepi/tools_ws/devel/setup.bash --extend 2>/dev/null || true
        source /home/orangepi/livox_ws/devel/setup.bash --extend 2>/dev/null || true
        source /home/orangepi/ctrl_ws/devel/setup.bash --extend 2>/dev/null || true
        export LD_PRELOAD=/home/orangepi/.local/lib/python3.8/site-packages/torch/lib/libgomp-d22c30c5.so.1
        """
        
        # 检查当前状态
        print("\n[2/5] 检查当前状态...")
        ssh_exec(client, f"{ros_env} echo 'ROS_DISTRO:' $ROS_DISTRO")
        
        # 编译 livox_ws
        print("\n[3/5] 编译 livox_ws（激光雷达驱动）...")
        ssh_exec(client, f"{ros_env} cd /home/orangepi/livox_ws && catkin_make", timeout=600)
        
        # 编译 tools_ws
        print("\n[4/5] 编译 tools_ws（SLAM 等）...")
        ssh_exec(client, f"{ros_env} cd /home/orangepi/tools_ws && catkin_make", timeout=600)
        
        # 编译 ctrl_ws
        print("\n[5/5] 编译 ctrl_ws（竞赛包）...")
        ssh_exec(client, f"{ros_env} cd /home/orangepi/ctrl_ws && catkin_make", timeout=600)
        
        # 验证编译结果
        print("\n" + "=" * 60)
        print("验证编译结果")
        print("=" * 60)
        
        ssh_exec(client, f"""
        {ros_env}
        echo ""
        echo "1. Livox 激光雷达驱动:"
        find /home/orangepi/livox_ws/devel/lib/livox_ros_driver2 -name "livox_ros_driver2_node" -type f 2>/dev/null || echo "   ✗ 节点未找到"
        echo ""
        echo "2. SLAM (fast_lio):"
        find /home/orangepi/tools_ws/devel/lib/fast_lio -name "fastlio_mapping" -type f 2>/dev/null || echo "   ✗ 节点未找到"
        echo ""
        echo "3. 竞赛包 (competition_pkg):"
        find /home/orangepi/ctrl_ws/devel/lib/competition_pkg -name "node_manage.py" -type f 2>/dev/null || echo "   ✗ 节点未找到"
        """)
        
        print("\n" + "=" * 60)
        print("编译完成！")
        print("=" * 60)
        print("\n下一步：")
        print("1. 在 OrangePi 上运行: bash self_start.sh")
        print("2. 启动 web_video_server: rosrun web_video_server web_video_server")
        print("3. 在地面站连接摄像头: http://10.209.49.217:8080/stream?topic=/camera/color/image_raw")
        
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        return 1
    finally:
        client.close()
        print("\nSSH 连接已关闭")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
