# Generator

`generate.py` 只使用 Python 标准库，根据上级目录的 `config.json` 生成确定性的 MySQL INSERT SQL。

直接运行：

```powershell
python demo/enterprise-finance/generator/generate.py
```

运行测试：

```powershell
python -m unittest discover -s demo/enterprise-finance/generator -p "test_*.py" -v
```

生成过程在写文件前执行以下内存校验：

- 表记录数和业务编号唯一性。
- 合同客户与订单客户一致，订单日期位于合同有效期内。
- 订单金额等于明细金额合计。
- `received_amount` 等于回款明细合计且不超过应收金额。
- A01-A06 实际数量与配置期望一致。

测试会使用同一配置生成两次 SQL，并比较 SHA-256 与完整字节内容。生成文件写入 `generated/`，不纳入 Git。
