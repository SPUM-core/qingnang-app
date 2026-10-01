"""测试 qingnang-APP backend 能否直接 import qingmeng_engine"""
import sys
try:
    sys.path.insert(0, r'e:\工作\qingmeng-engine')
    from qingmeng_engine._vendor.lunar_python import Solar
    print('✅ 直接 import 成功')

    # 测大运排盘
    solar = Solar.fromYmdHms(1986, 8, 2, 3, 0, 0)
    lunar = solar.getLunar()
    ec = lunar.getEightChar()
    print(f'八字: {ec.getYear()}{ec.getMonth()}{ec.getDay()}{ec.getTime()}')

    # 大运（阳男 = 男，顺排；ec.getDaYun() 需要性别）
    # lunar_python 的 DaYun 需要 gender_code: 1=男 0=女
    try:
        da_yun = ec.getDaYun(10, 1)  # 10段, 1=男
        for dy in da_yun:
            print(f'  大运 {dy.getStartYear()}~{dy.getEndYear()} ({dy.getStartAge()}~{dy.getEndAge()}) {dy.getGanZhi()}')
    except Exception as e:
        print(f'getDaYun error: {e}')
        # 看 Yun.py 接口
        yun = ec.getYun(10, 1)
        print(f'Yun type: {type(yun)}, methods: {[m for m in dir(yun) if not m.startswith("_")]}')
        try:
            dys = yun.getDaYun()
            for dy in dys[:3]:
                print(f'  {dy}')
        except Exception as e2:
            print(f'getDaYun from Yun: {e2}')
except ImportError as e:
    print(f'❌ import 失败: {e}')
