@echo off
echo Gerando codigo gRPC a partir do arquivo .proto...
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. aco_distributed.proto

if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo Codigo gRPC gerado com sucesso!
    echo Arquivos criados:
    echo   - aco_distributed_pb2.py
    echo   - aco_distributed_pb2_grpc.py
    echo ============================================
) else (
    echo.
    echo ERRO ao gerar codigo gRPC!
    echo Certifique-se de que grpcio-tools esta instalado:
    echo   pip install grpcio-tools
)
pause

