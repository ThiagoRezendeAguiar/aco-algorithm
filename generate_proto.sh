#!/bin/bash

echo "Gerando código gRPC a partir do arquivo .proto..."
python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. aco_distributed.proto

if [ $? -eq 0 ]; then
    echo ""
    echo "============================================"
    echo "Código gRPC gerado com sucesso!"
    echo "Arquivos criados:"
    echo "  - aco_distributed_pb2.py"
    echo "  - aco_distributed_pb2_grpc.py"
    echo "============================================"
else
    echo ""
    echo "ERRO ao gerar código gRPC!"
    echo "Certifique-se de que grpcio-tools está instalado:"
    echo "  pip install grpcio-tools"
fi

