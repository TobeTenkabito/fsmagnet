"""
一键构建脚本
执行步骤：
  1. 构建 Vue3 前端
  2. 运行 PyInstaller 打包
  3. 输出 dist/FSMagnet/FSMagnet.exe
"""
import os
import subprocess
import sys
import shutil

def step(msg: str):
    print(f"\n{'='*50}")
    print(f"  {msg}")
    print('='*50)

def build_frontend():
    step("① 构建 Vue3 前端")
    os.chdir("ui")
    subprocess.run(["npm", "install"], check=True)
    subprocess.run(["npm", "run", "build"], check=True)
    os.chdir("..")
    print("✅ 前端构建完成 → ui/dist/")

def build_exe():
    step("② PyInstaller 打包")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "fsmagnet.spec", "--clean"],
        check=True
    )
    print("✅ 打包完成 → dist/FSMagnet/FSMagnet.exe")

def post_clean():
    step("③ 清理临时文件")
    for d in ["build", "__pycache__"]:
        if os.path.exists(d):
            shutil.rmtree(d)
    print("✅ 清理完成")

if __name__ == "__main__":
    build_frontend()
    build_exe()
    post_clean()
    print("\n🎉 构建成功！输出目录: dist/FSMagnet/")