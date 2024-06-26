# -*- coding: utf-8 -*-
"""RAG_Application_Langchain_Pinecone.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1HXDEvbRNCl1O7cxd3cXrSNhwwB5MXjkq

# RAG Application using Google GenAi and Pinecone
-------------------------------

Basic Idea :

Taking `Youtube` video URL from user and then using `whisper` from `OPENAI` to transcribe the video transcript and then using that transcript to answer questions regarding the video, building a RAG Application.

Tech Stack : ``` 1. Langchain
             2. Openai
             3. HuggingFace
             4. Pinecone
             5. Google GenAI
             ```

### 1. Setting up the Environment
"""

import os
from dotenv import load_dotenv
load_dotenv()

GENAI_API_KEY = os.getenv("GENAI_API_KEY")

from langchain_google_genai import ChatGoogleGenerativeAI

model = ChatGoogleGenerativeAI(model='gemini-pro',
                               google_api_key=GENAI_API_KEY)

# model

# testing the model

model.invoke("What is the full form of ICC?")
# model.invoke("abcd")

"""The `AIMessage` contains the answer and use of `parser` to be done to extract the result"""

## impoting necessary libraries
from langchain_core.output_parsers import StrOutputParser

parser = StrOutputParser()

## initiating a chain, with the model and the parser
chain = model | parser

## testing the chain
chain.invoke("What is the full form of ICC in cricket?")

"""### 2. Introducing `Prompts` templates
-------------------------
"""

'''
We want to provide the model some context and then will ask some questions related to the context
'''

## importing necessary libraries
from langchain.prompts import ChatPromptTemplate

## creating a template
template = """
        Answer the question below based on the context provided. If you don't know the answer, reply with 'I don't know'.

        Context: {context}

        Question: {question}

"""

prompt = ChatPromptTemplate.from_template(template)
## getting the prompt
prompt.format(question="How many apples does Ram have?",
              context="Ram has 5 apples, one of them is rotten.He threw it out of the window.")

"""Prompt Template is working fine.

So, our model will work like, first the `prompt` will be provided both with the `question` and `context`, next a `query` will be run and the `model` will answer to that `query` and the `response` will be passed through the `parser` for `final answer`.
"""

## new chain, first prompt, then model, and then parser

chain = prompt | model | parser

chain.invoke({
    "context":"Full form of ICC is Indian Cricket Council.",
    "question":"What is the full form of ICC?"
})

"""**Conversion from One Language to another language**

chain will look like, the `prompt` will receive both `question` and `answer` and then the `prompt` will be forwarded to the `model`. The `response` we get, after providing `query` to the model, will pass through the `parser` and the result we receive from `parser` will be the input for the new `chain` where, the `prompt` will only accept the language name and the answer from previous reply. And the after passing through new `translation prompt`, the `model` will be responsible for providing the expected output after accepting the `query`, and finally the `parser` will give the final result.
"""

## creating translation template/prompt

translation_template = """
   Trnaslate the following sentence to the new language.

   Sentence: {sentence}

   New Language: {language}
"""
## prompt
translational_prompt = ChatPromptTemplate.from_template(translation_template)

## testing the prompt
# translational_prompt.format(sentence="I love you", language="Bengali")

from operator import itemgetter

## creating translation chain
translational_chain = (
    {"sentence":chain, "language":itemgetter("language")} | translational_prompt | model | parser
)

translational_chain.invoke({
    "context":"Netaji Subhas Chandra Bose was a great freedom fighter. He was born in Cuttack, Odisha. He was the leader of the Indian National Army.",
    "question":"What is the birthplace of Netaji Subhas Chandra Bose?",
    "language":"Bengali"
})

"""### 3. Transcribing the Youtube Video

OpenAI Whisper, python module - `whisper` can be used to transcribe any video. And the video script will be used as the context for the model to search result from.
"""

import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_KEY



## setting up whisper

import whisper
import tempfile
from pytube import YouTube
import numpy as np
import torch

# Use CUDA, if available
# DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

## various variables
YOUTUBE_VIDEO_URL = "https://youtu.be/NZZ0A0OWlkE?si=7cADG-K-tIOG7eeN"


## create trnascroption file only if the file is not already present
# transcription_file = os.path.join(os.getcwd(), "transcription.txt")
if not os.path.exists("transcription.txt"):
    youtube = YouTube(YOUTUBE_VIDEO_URL)
    audio = youtube.streams.filter(only_audio=True).first()
    # print(audio)

    # Load the desired model
    # whisper_model = whisper.load_model("medium.en").to(DEVICE)
    whisper_model = whisper.load_model("base.en")
    with tempfile.TemporaryDirectory() as tmpdir:
        file = audio.download(output_path=tmpdir)
        # file = audio.download(filename="sample.mp3")
        print(file) ## Debugging
        transcription = whisper_model.transcribe(file, fp16 = False)["text"]

    with open("transcription.txt", "w") as file:
        file.write(transcription)

## reading the text file [transcription.txt]

with open("transcription.txt", "r") as file:
    transcription = file.read()



"""### 4. Using the Entire Transcription as Context
------------------------
"""

##ctesting out one question based on whole context

try:
    chain.invoke({
        "question":"What the speaker is talking about?",
        "context":transcription
    })
except Exception as e:
    print(e)

"""Error code: 400 - {'error': {'message': "This model's maximum context length is 16385 tokens. However, your messages resulted in 47047 tokens. Please reduce the length of the messages.", 'type': 'invalid_request_error', 'param': 'messages', 'code': 'context_length_exceeded'}}"""



"""### 5. Splitting the Transcription
-------------------

As we can't use the whole transcription as context so we will be chunking the whole transcription into smaller chunks.

Loading the transcription into the memory
"""

from langchain_community.document_loaders import TextLoader

loader = TextLoader("transcription.txt")
text_document = loader.load()
# text_document

"""For our application, we will be using TextSplitter to create chunks of 1000 tokens, and 10% of overlapping for context remember"""

## importing libraries
from langchain.text_splitter import RecursiveCharacterTextSplitter

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
## aplying the text splitter
documents = text_splitter.split_documents(text_document)
len(documents) ## Total No of Chunks



"""### 6. Finding the Relevant Chunks
---------------------

Given a particular question, we need to find the relevant chunks from the transcription to send to the model. Here is where the idea of embeddings comes into play.

To provide with the most relevant chunks, we can use the embeddings of the question and the chunks of the transcription to compute the similarity between them. We can then select the chunks with the highest similarity to the question and use them as the context for the model
"""

## generating embeddings for the chunks


## importig necessary libraries
from langchain_google_genai import GoogleGenerativeAIEmbeddings

embedding = GoogleGenerativeAIEmbeddings(model="models/embedding-001",
                                          google_api_key=GENAI_API_KEY)

vector = embedding.embed_query("Swiggy is a food and grocery delivery company, headquartered in Bangalore, India")
print(f"Embedding Length: {len(vector)}")
print(vector[:5])

## simple comparison of embeddings
vector1 = embedding.embed_query("India is a country in Asia.")
vector2 = embedding.embed_query("Zomato is a food delivery company. It is headquartered in Gurgaon, India.")

"""We can now compute the similarity between the query and each of the two sentences. The closer the embeddings are, the more similar the sentences will be.

We can use Cosine Similarity to calculate the similarity between the query and each of the sentences:
"""

# importing cosine similarity

# from scipy.spatial.distance import cosine
from sklearn.metrics.pairwise import cosine_similarity

query_sentence1_similarity = cosine_similarity([vector], [vector1])[0][0]
query_sentence2_similarity = cosine_similarity([vector], [vector2])[0][0]

query_sentence1_similarity, query_sentence2_similarity

"""### 6. Setting Up a Vector Store
---------------------------------------------

Embedding model will be applied on all chunks and embedding vectors will be stored in a vector Store[VectorDB]

A vector store is a database of embeddings that specializes in fast similarity searches.
"""

## importing necessary libraries
from langchain_community.vectorstores import DocArrayInMemorySearch
from langchain.vectorstores import FAISS

# vectorstore = FAISS.from_documents(all_splits, embeddings)

vectorstore1 = FAISS.from_texts(
    [
        "Aman and Somen are brothers.",
        "Aman has a sister whose name is Riya.",
        "Riya is a doctor.",
        "Sayan loves to play football.",
        "Audi is a luxury car brand.",
        "Somen is a software engineer.",
        "Aman and Riya are siblings."
    ],
    embedding=embedding
)

# vectorstore1

## searching similar documents

retriever1 = vectorstore1.as_retriever()
vectorstore1.similarity_search_with_score(query = "What is the profession of Somen?", top_k=3)

"""### 7. Connecting `VectorStore` to the Chain
-------------------------------------------

We can use the vector store to find the most relevant chunks from the transcription to send to the model. Here is how we can connect the vector store to the chain:


We need to configure a Retriever. The retriever will run a similarity search in the vector store and return the most similar documents back to the next step in the chain.

We can get a retriever directly from the vector store
"""

## creating a retriver

retriever1 = vectorstore1.as_retriever()
retriever1.invoke("What is the relation between Sayan and Aman?")



"""Our prompt expects two parameters, "context" and "question." We can use the retriever to find the chunks we'll use as the context to answer the question.

We can create a map with the two inputs by using the RunnableParallel and RunnablePassthrough classes. This will allow us to pass the context and question to the prompt as a map with the keys "context" and "question."
"""

## importing necessary libraries

from langchain_core.runnables import RunnableParallel, RunnablePassthrough

setup = RunnableParallel(context = retriever1, question=RunnablePassthrough())
setup.invoke("What is the favourite sport of Sayan?")

chain = setup | prompt | model | parser
## testing the chain
chain.invoke("What is the profession of Riya?")

## another testing
chain.invoke("What type of car is Audi?")

"""### 8. Loading `transcription` into the vector store
-------------------------------------------------
"""

## initiating the vector store
vectorstore_transcription = FAISS.from_documents(documents, embedding)

"""Creating chain for the new vector store,

RunnableParallel and RunnablePassthrough will be used.
"""

chain = (
    {"context":vectorstore_transcription.as_retriever(), "question":RunnablePassthrough()}
    | prompt
    | model
    | parser
)

chain.invoke("When did her mom imegrate to the US?")

chain.invoke("Tell me about the speaker's first and second job.")



"""### 9. Setting Up the `PineCone`
-------------------------------------------

In practice, we need a vector store that can handle large amounts of data and perform similarity searches at scale. So we will be using `PineCone`
"""

## importing necessary libraries

from langchain_pinecone import PineconeVectorStore

## setting up the pinecone connection
index_name = "ytvideo-transcribing"

pinecone = PineconeVectorStore.from_documents(
    documents,
    embedding,
    index_name=index_name
)

"""Let's now run a similarity search on pinecone to make sure everything works"""

pinecone.similarity_search("What is speakers family background?")[:2]

## initiating the chain

chain = (
    {"context":pinecone.as_retriever(), "question":RunnablePassthrough()}
    | prompt
    | model
    | parser
)

## final example

chain.invoke("What is speakers family background?")