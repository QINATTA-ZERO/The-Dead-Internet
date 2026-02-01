from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Subreddit(Base):
    __tablename__ = "subreddits"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text)
    creator = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    posts = relationship("Post", back_populates="subreddit")
    subscribers = relationship("Subscription", back_populates="subreddit")

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user = Column(String, index=True)
    subreddit_id = Column(Integer, ForeignKey("subreddits.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    subreddit = relationship("Subreddit", back_populates="subscribers")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user = Column(String, index=True)
    type = Column(String) # 'reply', 'mention', 'system'
    content = Column(String)
    link = Column(String)
    is_read = Column(Integer, default=0) # 0=False, 1=True
    created_at = Column(DateTime, default=datetime.utcnow)

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    content = Column(Text)
    author = Column(String, index=True)
    subreddit_id = Column(Integer, ForeignKey("subreddits.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    score = Column(Integer, default=0)
    
    subreddit = relationship("Subreddit", back_populates="posts")
    comments = relationship("Comment", back_populates="post")
    votes = relationship("Vote", back_populates="post")

class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    author = Column(String)
    post_id = Column(Integer, ForeignKey("posts.id"))
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    score = Column(Integer, default=0)
    
    post = relationship("Post", back_populates="comments")
    replies = relationship("Comment", remote_side=[id])
    votes = relationship("Vote", back_populates="comment")

class Vote(Base):
    __tablename__ = "votes"
    id = Column(Integer, primary_key=True, index=True)
    user = Column(String)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    value = Column(Integer) # 1 for up, -1 for down
    
    post = relationship("Post", back_populates="votes")
    comment = relationship("Comment", back_populates="votes")
