# Aegis

A secure, scalable, and non-custodial Ethereum L2 powered by the Reserve RToken platform.

Aegis is a mythical shield in Greek mythology that protected Zeus and Athena in battle. In a similar fashion, the Aegis L2 is designed to protect users and their funds while they are conducting finance and commerce in an increasingly adversarial environment.

We envision a world where no one is unbanked and where anyone can participate in the global financial system that is fast, cheap and transparent while keeping custody of their money. To achieve our vision, we shall combine two powerful and synergistic technologies: the [Reserve protocol](https://reserve.org/en/protocol/) and the [NOCUST commit-chain](https://docs.ethhub.io/ethereum-roadmap/layer-2-scaling/commit-chains/).

# System Summary

Aegis has two main components:

1. Aegis Commit-chain - A chain of commits to the NOCUST smart contracts on Ethereum by centralized but trustless operators running the Aegis Hub server. The operators facilitate gas-less transactions off-chain without taking custody of user funds. 

2. Aegis USD (AUSD) stablecoin - an RToken that is designed to protect the funds of normal users who we envisage to be regular everyday people through collateral diversity and collateral default insurance. The fees for transacting on Aegis will be paid using AUSD.

# Aegis Commit-chain

Based on the [NOCUST commit-chain](https://docs.liquidity.network/background) technology developed by Liquidity Network. It is tightly integrated with the Aegis USD that serves as its native token to solve the drawbacks of the original NOCUST implementation. 

<p align="center">
   <img src="https://i.imgur.com/9ekBVjB.png" width=60% height=60%>
</p>

An Aegis Hub is a server that is run by an operator to interact with the Aegis commit-chain. It is a fork of the [NOCUST Hub server](https://github.com/liquidity-network/nocust-hub).

## NOCUST Pros and Cons

Benefits:
1. Non-custodial L1 Security 
2. [Unbounded Scalability](https://docs.liquidity.network/costs)
3. Superior User Experience

Drawbacks:
1. Weak Tokenomics
2. Lack of EVM Compatability

NOCUST whitepaper: https://eprint.iacr.org/2018/642.pdf

# RTokens x NOCUST

RTokens unleashes the potential of the NOCUST concept by improving the project tokenomics and wrapping DeFi into stablecoins circumventing the need for the L2 EVM. This provides a better user experience through fast and cheap transactions and by preserving composability on L1. 

# SPEAR Labs Team

SPEAR stands for Stablecoin Payments, Exchange And Remittances. 

# Disclaimer

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

 
