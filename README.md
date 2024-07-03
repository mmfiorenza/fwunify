## Protótipo de validação
Este repositório traz o protótipo FWunify, desenvolvido para gerenciamento de múltiplos firewalls em redes corporativas.

## Instalação do software
ATENÇÃO: Esse processo de instação/utilização foi testado e validado para Ubuntu 20.04. Instalações em outras distribuições podem necessitar ajustes.

Faça a instalação do GIT e do virtualenv:

`sudo apt-get install git virtualenv`
* Será solicitada a senha do usuário

Utilize os comandos abaixo para criar e ativar a virtualenv do projeto:

```bash
virtualenv venv_firewall --python=python3
source venv_firewall/bin/activate
cd venv_firewall
```

Faça o download do projeto utilizando git

`git clone https://github.com/mmfiorenza/fwunify`

Acesse a pasta do projeto.

`cd fwunify`

Execute o script "setup.sh" para instalação das dependências

`bash scripts/setup.sh`

* Poderá ser solicitada a senha de usuário para instalação dos pacotes

## Preparação da máquina
Para aplicar as regras traduzidas no firewall IPTables do sistema operacional, será necessário configurar o acesso SSH, bem como a criação de um usuário para este fim. 

Faça a instalação do servidor SSH:

`sudo apt-get install openssh-server -y`

Crie o usuário admin:

`sudo useradd admin ; sudo passwd admin`
* Quando solicitada a senha, digite "admin", sem aspas.

Execute o comando abaixo para ajustar as permissões:

`sudo usermod -G sudo admin`

Utilize o comando abaixo para testar a conexão:
`ssh admin@127.0.0.1`
* Quando solicitado digite "yes".
* Quando solicitado digite a senha "admin", sem aspas.
* Para sair, digite "exit"

## Uso
Certifique-se que esteja na virtualenv criada para o projeto, indicada por "(venv_firewall)" no console.
Caso não esteja, execute o comando abaixo:

`source ../bin/activate`

Execute os módulos tradutores utilizando o script “start_microservices.sh”

`bash scripts/start_microservices.sh`

Execute a API para recepção das intenções

`python src/api.py`


## Exemplo de uso

Em outro terminal, acesse a pasta com o exemplos de intenção:

`cd intent_examples`


Utilize comando curl para enviar a intenção em FWlang para a aplicação:

```bash
curl -u user1:user1 --data-binary "@intent_acl_1.txt" -X POST http://localhost:5000
```

Para verificar a aplicação da regra no firewall IPTables execute o comando:

`sudo iptables -L`

Para remover a regra, edite o arquivo substituindo o marcador "add" por "del" e faça o envio da intenção novamente com o comando curl, ou se preferir, execute o comando abaixo:

`sudo iptables -F`


## Ambientes
A ferramenta já foi testada e utilizada na prática nos seguintes ambientes/distribuições GNU/Linux:

Ubuntu 20.04:

 * `Kernel = 5.8.0-59-generic #66~20.04.1-Ubuntu SMP Thu Jun 17 2021 x86_64 GNU/Linux`
 * `Python = Python 3.8.10`


## Suporte
Este software não possui nenhuma forma de suporte. 

## Creditos
* Desenvolvimento: Maurício Fiorenza
* Orientação: Diego Kreutz
